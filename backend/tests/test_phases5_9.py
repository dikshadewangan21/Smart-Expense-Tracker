import json
from datetime import date, timedelta
from decimal import Decimal
from tests.conftest import auth, register

def test_onboarding_and_profile(client):
    token = register(client, "onboard@example.com", "secret-pass-123")
    r = client.post("/api/auth/onboarding", headers=auth(token), json={
        "name": "Alex",
        "currency": "INR",
        "monthly_income": 85000,
        "monthly_savings_target": 20000,
        "budgeting_style": "aggressive",
        "initial_account_name": "Main Checking",
        "initial_account_kind": "bank",
        "initial_account_balance": 50000,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["onboarded"] is True
    assert data["name"] == "Alex"
    assert data["currency"] == "INR"

def test_csv_import_and_deduplication(client):
    token = register(client, "csv@example.com", "secret-pass-123")

    csv_data = (
        "Date,Description,Amount,Type\n"
        "2026-10-01,Salary Employer,50000,income\n"
        "2026-10-02,Supermarket Groceries,2500,expense\n"
        "2026-10-02,Supermarket Groceries,2500,expense\n"  # Duplicate row inside file
    )

    # Preview
    r_prev = client.post("/api/imports/preview", headers=auth(token), files={
        "file": ("statement.csv", csv_data, "text/csv")
    })
    assert r_prev.status_code == 200
    prev_json = r_prev.json()
    assert "headers" in prev_json
    assert "detected_mapping" in prev_json

    # Execute import
    mapping = json.dumps({"date": 0, "merchant": 1, "amount": 2, "type": 3})
    r_exec = client.post("/api/imports/execute", headers=auth(token), files={
        "file": ("statement.csv", csv_data, "text/csv")
    }, data={"mapping": mapping})
    assert r_exec.status_code == 200
    res = r_exec.json()
    assert res["rows_total"] == 3
    assert res["rows_imported"] == 2
    assert res["rows_duplicate"] == 1

    # Second import of same file should have all duplicates
    r_exec2 = client.post("/api/imports/execute", headers=auth(token), files={
        "file": ("statement.csv", csv_data, "text/csv")
    }, data={"mapping": mapping})
    assert r_exec2.status_code == 200
    assert r_exec2.json()["rows_duplicate"] == 3
    assert r_exec2.json()["rows_imported"] == 0

    # History
    r_hist = client.get("/api/imports", headers=auth(token))
    assert r_hist.status_code == 200
    assert len(r_hist.json()) == 2

def test_receipt_ocr_and_confirmation(client):
    token = register(client, "receipt@example.com", "secret-pass-123")

    receipt_text = (
        "Starbucks Coffee\n"
        "Date: 2026-10-04\n"
        "Caramel Macchiato 350.00\n"
        "Blueberry Muffin 220.00\n"
        "Tax Amount: 50.00\n"
        "Total Amount: 620.00\n"
    )

    r_up = client.post("/api/receipts/upload", headers=auth(token), files={
        "file": ("receipt.txt", receipt_text.encode("utf-8"), "text/plain")
    })
    assert r_up.status_code == 200
    rec = r_up.json()
    assert rec["merchant"] == "Starbucks Coffee"
    assert rec["total"] == 620.0 or rec["total"] == "620.00"
    assert rec["status"] == "pending_review"
    assert len(rec["items"]) >= 1

    # Confirm receipt as transaction
    r_conf = client.post(f"/api/receipts/{rec['id']}/confirm", headers=auth(token), json={
        "merchant": "Starbucks Coffee",
        "amount": 620.0,
        "date": "2026-10-04",
        "payment_method": "upi",
    })
    assert r_conf.status_code == 200
    tx_id = r_conf.json()["transaction_id"]
    assert tx_id is not None

    # Check transaction exists
    tx_resp = client.get(f"/api/transactions/{tx_id}", headers=auth(token))
    assert tx_resp.status_code == 200
    assert tx_resp.json()["merchant"] == "Starbucks Coffee"
    assert tx_resp.json()["source"] == "ocr"

def test_ai_coach_and_quick_add(client):
    token = register(client, "coach@example.com", "secret-pass-123")

    # Quick Add parsing
    r_qa = client.post("/api/coach/quick-add", headers=auth(token), json={
        "text": "spent 450 at Swiggy yesterday using upi"
    })
    assert r_qa.status_code == 200
    qa_data = r_qa.json()
    assert qa_data["type"] == "expense"
    assert qa_data["amount"] == 450.0 or qa_data["amount"] == "450"
    assert "swiggy" in qa_data["merchant"].lower()
    assert qa_data["payment_method"] == "upi"
    assert qa_data["date"] == (date.today() - timedelta(days=1)).isoformat()

    # NL Search parsing
    r_nl = client.get("/api/coach/nl-search?q=swiggy above 300 this month", headers=auth(token))
    assert r_nl.status_code == 200
    nl_data = r_nl.json()
    assert "min_amount" in nl_data
    assert "date_from" in nl_data

    # Coach Chat
    r_chat = client.post("/api/coach/chat", headers=auth(token), json={
        "prompt": "How is my budget looking this month?"
    })
    assert r_chat.status_code == 200
    c_resp = r_chat.json()
    assert "message" in c_resp
    assert "content" in c_resp["message"]
    assert len(c_resp["message"]["content"]) > 10

def test_notifications_evaluation(client):
    token = register(client, "notif@example.com", "secret-pass-123")

    # Add a bill due in 3 days
    due = (date.today() + timedelta(days=3)).isoformat()
    client.post("/api/bills", headers=auth(token), json={
        "name": "Broadband Internet",
        "amount": 999.0,
        "due_date": due,
        "frequency": "monthly",
        "reminder_days": [7, 3, 1, 0]
    })

    # Trigger evaluation
    r_eval = client.post("/api/notifications/evaluate", headers=auth(token))
    assert r_eval.status_code == 200
    assert r_eval.json()["new_alerts_created"] >= 1

    # List notifications
    r_list = client.get("/api/notifications", headers=auth(token))
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    assert len(items) >= 1
    notif_id = items[0]["id"]

    # Mark read
    r_read = client.patch(f"/api/notifications/{notif_id}/read", headers=auth(token))
    assert r_read.status_code == 200

    # Mark all read
    r_all = client.post("/api/notifications/read-all", headers=auth(token))
    assert r_all.status_code == 200

def test_safe_to_spend_and_timeline(client):
    token = register(client, "safe@example.com", "secret-pass-123")

    # Add checking account with balance
    client.post("/api/accounts", headers=auth(token), json={
        "name": "HDFC Checking",
        "kind": "bank",
        "opening_balance": 50000.0,
    })

    # Safe to spend
    r_safe = client.get("/api/planning/safe-to-spend", headers=auth(token))
    assert r_safe.status_code == 200
    s_data = r_safe.json()
    assert "safe_to_spend_daily" in s_data
    assert float(s_data["safe_to_spend_total"]) > 0

    # Timeline
    r_time = client.get("/api/planning/timeline?days=45", headers=auth(token))
    assert r_time.status_code == 200
    t_data = r_time.json()
    assert len(t_data["points"]) == 45
    assert "projected_balance" in t_data["points"][0]

def test_shared_finances(client):
    token1 = register(client, "u1@example.com", "pass-123456789")
    token2 = register(client, "u2@example.com", "pass-123456789")

    # User 1 creates group
    r_grp = client.post("/api/shared/groups", headers=auth(token1), json={
        "name": "Goa Trip",
        "kind": "trip"
    })
    assert r_grp.status_code == 201
    grp = r_grp.json()
    grp_id = grp["id"]

    # Add User 2
    r_add = client.post(f"/api/shared/groups/{grp_id}/members", headers=auth(token1), json={
        "email": "u2@example.com"
    })
    assert r_add.status_code == 200

    # Add expense paid by User 1 for 2000 split equally
    u1_id = grp["members"][0]["user_id"]
    r_exp = client.post(f"/api/shared/groups/{grp_id}/expenses", headers=auth(token1), json={
        "description": "Hotel Resort",
        "amount": 2000.0,
        "date": "2026-10-05",
        "paid_by": u1_id,
        "split_type": "equal",
    })
    assert r_exp.status_code == 201
    grp_updated = r_exp.json()
    assert len(grp_updated["expenses"]) == 1
    assert len(grp_updated["settlements"]) == 1
    assert grp_updated["settlements"][0]["amount"] == 1000.0

def test_privacy_and_exports(client):
    token = register(client, "priv@example.com", "pass-123456789")

    # Add transaction
    client.post("/api/transactions", headers=auth(token), json={
        "type": "expense",
        "amount": 120.0,
        "merchant": "Chai Point",
        "date": "2026-10-04",
    })

    # Export CSV
    r_csv = client.get("/api/privacy/export/csv", headers=auth(token))
    assert r_csv.status_code == 200
    assert "Chai Point" in r_csv.text

    # Export JSON takeout
    r_json = client.get("/api/privacy/export/json", headers=auth(token))
    assert r_json.status_code == 200
    takeout = r_json.json()
    assert "user" in takeout
    assert len(takeout["transactions"]) == 1

    # Audit logs
    r_audit = client.get("/api/privacy/audit-logs", headers=auth(token))
    assert r_audit.status_code == 200

    # Delete Account
    r_del = client.post("/api/privacy/delete-account", headers=auth(token), json={
        "password": "pass-123456789"
    })
    assert r_del.status_code == 204

    # Sign in should now fail
    r_fail = client.post("/api/auth/login", json={"email": "priv@example.com", "password": "pass-123456789"})
    assert r_fail.status_code == 401
