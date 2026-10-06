from decimal import Decimal

from tests.conftest import auth, register


def cats(client, token):
    return {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth(token)).json()}


def make(client, token, **over):
    body = {"type": "expense", "amount": "100.00", "date": "2026-10-02", "merchant": "Test Store"}
    body.update(over)
    r = client.post("/api/transactions", json=body, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def test_default_categories_seeded(client):
    t = register(client)
    c = cats(client, t)
    assert {"Food", "Rent", "Salary"} <= set(c)


def test_create_edit_delete_roundtrip(client):
    t = register(client)
    c = cats(client, t)
    tx = make(client, t, merchant="Cafe One", category_id=c["Food"], tags=["Work", "work", " lunch "])
    assert tx["category"] == "Food" and tx["tags"] == ["lunch", "work"] and Decimal(str(tx["amount"])) == 100

    upd = {"type": "expense", "amount": "250.50", "date": "2026-10-03", "merchant": "Cafe One",
           "category_id": c["Food"], "payment_method": "upi", "tags": []}
    r = client.put(f"/api/transactions/{tx['id']}", json=upd, headers=auth(t))
    assert r.status_code == 200 and Decimal(str(r.json()["amount"])) == Decimal("250.50") and r.json()["tags"] == []

    assert client.delete(f"/api/transactions/{tx['id']}", headers=auth(t)).status_code == 204
    assert client.get(f"/api/transactions/{tx['id']}", headers=auth(t)).status_code == 404


def test_validation(client):
    t = register(client)
    for bad in ({"amount": "0"}, {"amount": "-5"}, {"amount": "12.345"}, {"type": "bogus"}, {"payment_method": "bitcoin"}):
        body = {"type": "expense", "amount": "10", "date": "2026-10-02", **bad}
        assert client.post("/api/transactions", json=body, headers=auth(t)).status_code == 422, bad


def test_category_kind_must_match_type(client):
    t = register(client)
    c = cats(client, t)
    r = client.post("/api/transactions", json={"type": "expense", "amount": "10", "date": "2026-10-02",
                                           "category_id": c["Salary"]}, headers=auth(t))
    assert r.status_code == 422


def test_cannot_touch_or_reference_another_users_data(client):
    ta = register(client, "a@example.com")
    tx = make(client, ta)
    ca = cats(client, ta)
    acc = client.post("/api/accounts", json={"name": "Mine", "kind": "bank"}, headers=auth(ta)).json()

    client.cookies.clear()
    tb = register(client, "b@example.com")
    assert client.get(f"/api/transactions/{tx['id']}", headers=auth(tb)).status_code == 404
    assert client.delete(f"/api/transactions/{tx['id']}", headers=auth(tb)).status_code == 404
    assert client.post(f"/api/transactions/{tx['id']}/duplicate", headers=auth(tb)).status_code == 404
    body = {"type": "expense", "amount": "5", "date": "2026-10-02"}
    assert client.put(f"/api/transactions/{tx['id']}", json=body, headers=auth(tb)).status_code == 404
    assert client.post("/api/transactions", json={**body, "category_id": ca["Food"]}, headers=auth(tb)).status_code == 422
    assert client.post("/api/transactions", json={**body, "account_id": acc["id"]}, headers=auth(tb)).status_code == 422
    assert client.get("/api/transactions", headers=auth(tb)).json()["total"] == 0
    # A's data is untouched
    assert client.get(f"/api/transactions/{tx['id']}", headers=auth(ta)).status_code == 200


def test_filters_sort_and_search(client):
    t = register(client)
    c = cats(client, t)
    make(client, t, merchant="Swiggy", amount="350", payment_method="upi", category_id=c["Food"], date="2026-09-15")
    make(client, t, merchant="Amazon", amount="2500", payment_method="credit_card", date="2026-10-01", tags=["gift"])
    make(client, t, merchant="Uber", amount="180", payment_method="upi", date="2026-10-02")
    make(client, t, type="income", merchant="Employer", amount="50000", category_id=c["Salary"], date="2026-10-01")

    def q(**p):
        r = client.get("/api/transactions", params=p, headers=auth(t))
        assert r.status_code == 200, r.text
        return r.json()

    assert q()["total"] == 4
    assert [i["merchant"] for i in q(q="swig")["items"]] == ["Swiggy"]
    assert q(type="income")["total"] == 1
    assert q(min_amount=2000, type="expense")["total"] == 1
    assert q(payment_method="upi")["total"] == 2
    assert q(date_from="2026-10-01", date_to="2026-10-01")["total"] == 2
    assert q(tag="gift")["total"] == 1
    assert q(category_id=c["Food"])["total"] == 1
    assert [i["amount"] for i in q(sort="amount", order="asc")["items"]][0] in (180, 180.0, "180.00")
    assert q(q="%")["total"] == 0  # LIKE wildcards are escaped, not interpreted


def test_pagination_and_page_size_cap(client):
    t = register(client)
    for i in range(7):
        make(client, t, amount=str(10 + i))
    p = client.get("/api/transactions", params={"page": 2, "page_size": 3}, headers=auth(t)).json()
    assert p["total"] == 7 and len(p["items"]) == 3 and p["page"] == 2
    assert client.get("/api/transactions", params={"page_size": 101}, headers=auth(t)).status_code == 422
    assert client.get("/api/transactions", params={"page": 0}, headers=auth(t)).status_code == 422


def test_merchant_rule_learning(client):
    t = register(client)
    c = cats(client, t)
    # Built-in keyword table suggests a category when none is given
    assert make(client, t, merchant="Swiggy Order")["category"] == "Food"
    # A one-off correction does NOT create a rule
    tx = make(client, t, merchant="Corner Shop XYZ")
    body = {"type": "expense", "amount": "100", "date": "2026-10-02", "merchant": "Corner Shop XYZ",
            "category_id": c["Groceries"]}
    client.put(f"/api/transactions/{tx['id']}", json=body, headers=auth(t))
    assert make(client, t, merchant="Corner Shop XYZ")["category"] is None
    # With always_categorize the rule is learned and applied to later transactions (case-insensitive)
    client.put(f"/api/transactions/{tx['id']}", json={**body, "always_categorize": True}, headers=auth(t))
    assert make(client, t, merchant="corner shop xyz")["category"] == "Groceries"
    # A learned rule overrides the built-in table
    sw = make(client, t, merchant="Swiggy Instamart")
    client.put(f"/api/transactions/{sw['id']}", json={"type": "expense", "amount": "100", "date": "2026-10-02",
               "merchant": "Swiggy Instamart", "category_id": c["Groceries"], "always_categorize": True}, headers=auth(t))
    assert make(client, t, merchant="Swiggy Instamart")["category"] == "Groceries"


def test_rules_are_per_user(client):
    ta = register(client, "a@example.com")
    tx = make(client, ta, merchant="Shared Name")
    ca = cats(client, ta)
    client.put(f"/api/transactions/{tx['id']}", json={"type": "expense", "amount": "1", "date": "2026-10-02",
               "merchant": "Shared Name", "category_id": ca["Travel"], "always_categorize": True}, headers=auth(ta))
    client.cookies.clear()
    tb = register(client, "b@example.com")
    assert make(client, tb, merchant="Shared Name")["category"] is None


def test_duplicate(client):
    t = register(client)
    tx = make(client, t, merchant="Repeat", tags=["x"])
    d = client.post(f"/api/transactions/{tx['id']}/duplicate", headers=auth(t)).json()
    assert d["id"] != tx["id"] and d["merchant"] == "Repeat" and d["tags"] == ["x"]
    assert client.get("/api/transactions", headers=auth(t)).json()["total"] == 2


def test_split_must_sum_exactly_and_is_atomic(client):
    t = register(client)
    c = cats(client, t)
    tx = make(client, t, amount="287.00", merchant="Reliance Smart")
    bad = client.post(f"/api/transactions/{tx['id']}/split", headers=auth(t), json={"parts": [
        {"category_id": c["Groceries"], "amount": "200"}, {"category_id": c["Other"], "amount": "86.99"}]})
    assert bad.status_code == 422
    assert client.get("/api/transactions", headers=auth(t)).json()["total"] == 1  # nothing changed

    ok = client.post(f"/api/transactions/{tx['id']}/split", headers=auth(t), json={"parts": [
        {"category_id": c["Groceries"], "amount": "242.00"}, {"category_id": c["Other"], "amount": "45.00"}]})
    assert ok.status_code == 200
    items = client.get("/api/transactions", headers=auth(t)).json()["items"]
    assert len(items) == 2 and sum(Decimal(str(i["amount"])) for i in items) == Decimal("287.00")
    assert client.post(f"/api/transactions/{tx['id']}/split", headers=auth(t),
                       json={"parts": [{"amount": "287"}]}).status_code == 422  # needs >= 2 parts


def test_budget_upsert_and_live_status(client):
    t = register(client)
    c = cats(client, t)
    make(client, t, amount="700", category_id=c["Food"], date="2026-10-05")
    r = client.post("/api/budgets", headers=auth(t), json={
        "month": "2026-10-17", "total_limit": "10000",
        "categories": [{"category_id": c["Food"], "limit_amount": "1000"}]})
    assert r.status_code == 201
    b = client.get("/api/budgets", params={"month": "2026-10-01"}, headers=auth(t)).json()["budget"]
    line = b["categories"][0]
    assert Decimal(str(line["used"])) == 700 and Decimal(str(line["remaining"])) == 300 and line["percent_used"] == 70.0

    # Replacing, not duplicating
    client.post("/api/budgets", headers=auth(t), json={"month": "2026-10-01", "total_limit": "9000", "categories": []})
    b = client.get("/api/budgets", params={"month": "2026-10-01"}, headers=auth(t)).json()["budget"]
    assert Decimal(str(b["total_limit"])) == 9000 and b["categories"] == []

    over = client.post("/api/budgets", headers=auth(t), json={"month": "2026-10-01", "total_limit": "500",
                       "categories": [{"category_id": c["Food"], "limit_amount": "1000"}]})
    assert over.status_code == 422
    dup = client.post("/api/budgets", headers=auth(t), json={"month": "2026-10-01", "total_limit": "5000", "categories": [
        {"category_id": c["Food"], "limit_amount": "1"}, {"category_id": c["Food"], "limit_amount": "2"}]})
    assert dup.status_code == 422


def test_budget_rejects_other_users_category(client):
    ta = register(client, "a@example.com")
    ca = cats(client, ta)
    client.cookies.clear()
    tb = register(client, "b@example.com")
    r = client.post("/api/budgets", headers=auth(tb), json={"month": "2026-10-01", "total_limit": "100",
                    "categories": [{"category_id": ca["Food"], "limit_amount": "10"}]})
    assert r.status_code == 422
