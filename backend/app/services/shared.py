from collections import defaultdict
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import GroupExpense, GroupMember, SharedGroup, User

ZERO = Decimal("0")

def create_group(db: Session, user: User, name: str, kind: str = "friends") -> SharedGroup:
    group = SharedGroup(owner_id=user.id, name=name.strip(), kind=kind)
    db.add(group)
    db.flush()

    # Add owner as confirmed member
    member = GroupMember(group_id=group.id, user_id=user.id, status="accepted")
    db.add(member)
    db.commit()
    return group

def list_user_groups(db: Session, user_id: int) -> list[dict]:
    # User is member or owner
    group_ids = select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    groups = db.scalars(select(SharedGroup).where(SharedGroup.id.in_(group_ids)).order_by(SharedGroup.id.desc())).all()
    return [get_group_detail(db, g.id, user_id) for g in groups]

def get_group_detail(db: Session, group_id: int, user_id: int) -> dict:
    group = db.scalar(select(SharedGroup).where(SharedGroup.id == group_id))
    if not group:
        return {}

    members_raw = db.execute(
        select(GroupMember, User.name, User.email)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group.id)
    ).all()
    members = [{
        "user_id": gm.user_id,
        "name": uname or uemail.split("@")[0],
        "email": uemail,
        "status": gm.status,
    } for gm, uname, uemail in members_raw]

    expenses_raw = db.scalars(
        select(GroupExpense).where(GroupExpense.group_id == group.id).order_by(GroupExpense.date.desc(), GroupExpense.id.desc())
    ).all()

    user_names = {m["user_id"]: m["name"] for m in members}

    # Calculate net balances and settlements
    # net_balance = total_paid - total_share
    net_balances: dict[int, Decimal] = defaultdict(lambda: ZERO)
    expenses_out = []

    for exp in expenses_raw:
        net_balances[exp.paid_by] += exp.amount
        for uid_str, share in exp.splits.items():
            uid = int(uid_str)
            net_balances[uid] -= Decimal(str(share))

        expenses_out.append({
            "id": exp.id,
            "description": exp.description,
            "amount": float(exp.amount),
            "date": exp.date.isoformat(),
            "paid_by": exp.paid_by,
            "paid_by_name": user_names.get(exp.paid_by, "Unknown"),
            "splits": exp.splits,
            "settled": exp.settled,
        })

    # Settlement calculations
    debtors = []
    creditors = []
    for uid, bal in net_balances.items():
        if bal < -Decimal("0.01"):
            debtors.append({"user_id": uid, "name": user_names.get(uid, "Unknown"), "amount": abs(bal)})
        elif bal > Decimal("0.01"):
            creditors.append({"user_id": uid, "name": user_names.get(uid, "Unknown"), "amount": bal})

    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)

    settlements = []
    d_idx, c_idx = 0, 0
    while d_idx < len(debtors) and c_idx < len(creditors):
        deb = debtors[d_idx]
        cred = creditors[c_idx]
        settle_amt = min(deb["amount"], cred["amount"])

        if settle_amt > Decimal("0.01"):
            settlements.append({
                "from_user_id": deb["user_id"],
                "from_name": deb["name"],
                "to_user_id": cred["user_id"],
                "to_name": cred["name"],
                "amount": float(settle_amt.quantize(Decimal("0.01"))),
            })

        deb["amount"] -= settle_amt
        cred["amount"] -= settle_amt

        if deb["amount"] <= Decimal("0.01"):
            d_idx += 1
        if cred["amount"] <= Decimal("0.01"):
            c_idx += 1

    return {
        "id": group.id,
        "name": group.name,
        "kind": group.kind,
        "owner_id": group.owner_id,
        "members": members,
        "expenses": expenses_out,
        "balances": [{
            "user_id": m["user_id"],
            "name": m["name"],
            "net_balance": float(net_balances[m["user_id"]].quantize(Decimal("0.01"))),
        } for m in members],
        "settlements": settlements,
    }

def add_member(db: Session, group_id: int, email: str) -> dict:
    target_user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not target_user:
        return {"error": "User with this email not found."}

    existing = db.scalar(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == target_user.id))
    if existing:
        return {"error": "User is already a member of this group."}

    gm = GroupMember(group_id=group_id, user_id=target_user.id, status="accepted")
    db.add(gm)
    db.commit()
    return {"status": "ok", "user_id": target_user.id, "name": target_user.name or target_user.email}

def add_expense(
    db: Session,
    group_id: int,
    paid_by: int,
    amount: Decimal,
    description: str,
    exp_date: date,
    split_type: str = "equal",
    custom_splits: dict[int, Decimal] | None = None,
) -> GroupExpense:
    members = db.scalars(select(GroupMember.user_id).where(GroupMember.group_id == group_id)).all()
    if not members:
        raise ValueError("Group has no members.")

    splits_dict = {}
    if split_type == "equal":
        share = (amount / Decimal(len(members))).quantize(Decimal("0.01"))
        remainder = amount - (share * Decimal(len(members)))
        for i, uid in enumerate(members):
            cur_share = share + (remainder if i == 0 else ZERO)
            splits_dict[str(uid)] = float(cur_share)
    else:
        if custom_splits:
            splits_dict = {str(k): float(Decimal(str(v))) for k, v in custom_splits.items()}
        else:
            raise ValueError("Custom splits must be specified.")

    expense = GroupExpense(
        group_id=group_id,
        paid_by=paid_by,
        amount=amount,
        description=description.strip(),
        date=exp_date,
        splits=splits_dict,
        settled=False,
    )
    db.add(expense)
    db.commit()
    return expense

def delete_expense(db: Session, group_id: int, expense_id: int) -> bool:
    exp = db.scalar(select(GroupExpense).where(GroupExpense.id == expense_id, GroupExpense.group_id == group_id))
    if exp:
        db.delete(exp)
        db.commit()
        return True
    return False
