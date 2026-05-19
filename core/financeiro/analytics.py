from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any
import unicodedata

from config import db

MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

COMPANY_NAME = "123 Caca Vazamentos"


def _branch(*parts: str) -> Any:
    node = db
    for part in parts:
        node = node.child(part)
    return node.get().val() or {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0

    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _currency(value: float) -> str:
    negative = value < 0
    formatted = f"{abs(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-R$ {formatted}" if negative else f"R$ {formatted}"


def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    clean = "".join(char.lower() if char.isalnum() else "-" for char in normalized)
    return "-".join(part for part in clean.split("-") if part)


def _safe_divide(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def _normalize_category_label(value: Any) -> str:
    clean = " ".join(str(value or "").split())
    return clean or "Sem categoria"


def _category_key(value: Any) -> str:
    label = _normalize_category_label(value)
    slug = _slugify(label)
    return slug or label.lower()


def _is_service_category(value: Any) -> bool:
    return _category_key(value).startswith("servi")


def list_destinatarios() -> dict[str, str]:
    raw_destinations = _as_dict(_branch("financeiro", "destinarios"))
    if raw_destinations:
        return raw_destinations

    derived_names = {COMPANY_NAME, "123 Caça Vazamentos"}
    transactions_root = _as_dict(_branch("financeiro", "transactions"))

    for year_data in transactions_root.values():
        for month_data in _as_dict(year_data).values():
            for day_data in _as_dict(month_data).values():
                for transaction in _as_dict(_as_dict(day_data).get("transactions")).values():
                    destination = str(_as_dict(transaction).get("destinatario", "")).strip()
                    source = str(_as_dict(transaction).get("origem", "")).strip()
                    if destination:
                        derived_names.add(destination)
                    if source:
                        derived_names.add(source)

    return {f"derived_{index:03d}": name for index, name in enumerate(sorted(derived_names), start=1)}


def load_manual_transactions() -> list[dict[str, Any]]:
    transactions_root = _as_dict(_branch("financeiro", "transactions"))
    transactions: list[dict[str, Any]] = []

    for year, year_data in transactions_root.items():
        for month, month_data in _as_dict(year_data).items():
            for day, day_data in _as_dict(month_data).items():
                for transaction_id, transaction in _as_dict(_as_dict(day_data).get("transactions")).items():
                    entry = _as_dict(transaction)
                    amount = _to_float(entry.get("amount"))
                    tx_type = str(entry.get("type", "d")).lower()
                    signed_amount = amount if tx_type == "c" else -amount
                    date_iso = f"{year}-{month}-{day}"
                    transactions.append(
                        {
                            "id": transaction_id,
                            "numero_transaction": entry.get("numero_transaction"),
                            "date_iso": date_iso,
                            "date_label": f"{day}/{month}/{year}",
                            "year": int(year),
                            "month": int(month),
                            "day": int(day),
                            "timestamp": entry.get("timestamp", 0),
                            "user": entry.get("user", "-"),
                            "origem": entry.get("origem", "-"),
                            "id_origem": entry.get("id_origem", ""),
                            "category": entry.get("category", "Sem categoria"),
                            "especie": entry.get("especie", "-"),
                            "destinatario": entry.get("destinatario", "-"),
                            "description": entry.get("description", ""),
                            "type": tx_type,
                            "type_label": "Credito" if tx_type == "c" else "Debito",
                            "amount": amount,
                            "signed_amount": signed_amount,
                            "amount_display": _currency(amount),
                            "signed_amount_display": _currency(signed_amount),
                            "observacao": entry.get("observacao", ""),
                        }
                    )

    transactions.sort(key=lambda item: (item["year"], item["month"], item["day"], item["timestamp"], str(item["id"])))
    return transactions


def load_pending_os() -> list[dict[str, Any]]:
    pending_root = _as_dict(_branch("financeiro", "transactions_pendentes"))
    entries: list[dict[str, Any]] = []

    for year, year_data in pending_root.items():
        for month, month_data in _as_dict(year_data).items():
            for day, day_data in _as_dict(month_data).items():
                for transaction_id, transaction in _as_dict(day_data).items():
                    item = _as_dict(transaction)
                    amount = _to_float(item.get("valor_empresa") or item.get("valor_liquido") or item.get("valor_recebido"))
                    payment_date = _to_date(item.get("date_payment")) or _to_date(f"{year}-{month}-{day}")
                    entries.append(
                        {
                            "id": transaction_id,
                            "year": int(year),
                            "month": int(month),
                            "day": int(day),
                            "date_payment": payment_date,
                            "city_os": item.get("city_os", "-"),
                            "tecnico": item.get("tecnico", "-"),
                            "tecnico_id": item.get("tecnico_id", ""),
                            "numero_os": item.get("numero_os", "-"),
                            "service": item.get("service", "-"),
                            "client": item.get("client", "-"),
                            "metodo_pagamento": item.get("metodo_pagamento", "-"),
                            "amount": amount,
                            "amount_display": _currency(amount),
                            "valor_empresa": _to_float(item.get("valor_empresa")),
                            "valor_tecnico": _to_float(item.get("valor_tecnico")),
                            "valor_liquido": _to_float(item.get("valor_liquido")),
                            "valor_recebido": _to_float(item.get("valor_recebido")),
                            "taxa": _to_float(item.get("taxa")),
                            "outros_custos_service": _to_float(item.get("outros_custos_service")),
                        }
                    )

    entries.sort(key=lambda item: ((item["date_payment"] or date.max), item["tecnico"], item["numero_os"]))
    return entries


def load_confirmed_os() -> list[dict[str, Any]]:
    confirmed_root = _as_dict(_branch("financeiro", "transactions_confirmadas"))
    entries: list[dict[str, Any]] = []

    for year, year_data in confirmed_root.items():
        for month, month_data in _as_dict(year_data).items():
            for day, day_data in _as_dict(month_data).items():
                for transaction_id, transaction in _as_dict(day_data).items():
                    item = _as_dict(transaction)
                    amount = _to_float(item.get("valor_empresa") or item.get("valor_liquido") or item.get("valor_recebido"))
                    payment_date = _to_date(item.get("date_payment")) or _to_date(f"{year}-{month}-{day}")
                    entries.append(
                        {
                            "id": transaction_id,
                            "year": int(year),
                            "month": int(month),
                            "day": int(day),
                            "date_payment": payment_date,
                            "city_os": item.get("city_os", "-"),
                            "tecnico": item.get("tecnico", "-"),
                            "tecnico_id": item.get("tecnico_id", ""),
                            "numero_os": item.get("numero_os", "-"),
                            "service": item.get("service", "-"),
                            "client": item.get("client", "-"),
                            "amount": amount,
                            "amount_display": _currency(amount),
                            "valor_empresa": _to_float(item.get("valor_empresa")),
                            "valor_tecnico": _to_float(item.get("valor_tecnico")),
                            "valor_liquido": _to_float(item.get("valor_liquido")),
                            "valor_recebido": _to_float(item.get("valor_recebido")),
                            "taxa": _to_float(item.get("taxa")),
                            "outros_custos_service": _to_float(item.get("outros_custos_service")),
                        }
                    )

    entries.sort(key=lambda item: ((item["date_payment"] or date.min), item["tecnico"], item["numero_os"]), reverse=True)
    return entries


def load_scheduled_transactions() -> dict[str, list[dict[str, Any]]]:
    scheduled_root = _as_dict(_branch("financeiro", "transactions_programadas"))

    def flatten(bucket_name: str) -> list[dict[str, Any]]:
        bucket = _as_dict(scheduled_root.get(bucket_name))
        items: list[dict[str, Any]] = []
        for year, year_data in bucket.items():
            for month, month_data in _as_dict(year_data).items():
                for transaction_id, transaction in _as_dict(month_data).items():
                    item = _as_dict(transaction)
                    due_date = _to_date(item.get("vencimento"))
                    amount = _to_float(item.get("amount") or item.get("valorpago"))
                    tx_type = str(item.get("type", "d")).lower()
                    signed_amount = amount if tx_type == "c" else -amount
                    items.append(
                        {
                            "id": transaction_id,
                            "year": int(year),
                            "month": int(month),
                            "due_date": due_date,
                            "origem": item.get("origem", "-"),
                            "destinatario": item.get("destinatario", "-"),
                            "description": item.get("description", ""),
                            "category": item.get("category", "Sem categoria"),
                            "type": tx_type,
                            "signed_amount": signed_amount,
                            "amount": amount,
                            "amount_display": _currency(amount),
                        }
                    )
        items.sort(key=lambda item: ((item["due_date"] or date.max), item["description"]))
        return items

    return {"pending": flatten("pedding"), "paid": flatten("paid")}


def load_attendance_records() -> list[dict[str, Any]]:
    attendance_root = _as_dict(_branch("attendance_records"))
    records: list[dict[str, Any]] = []

    for city, city_data in attendance_root.items():
        for year, year_data in _as_dict(city_data).items():
            for month, month_data in _as_dict(year_data).items():
                for day, day_data in _as_dict(month_data).items():
                    for record_id, record in _as_dict(day_data).items():
                        item = _as_dict(record)
                        records.append(
                            {
                                "id": record_id,
                                "city": city,
                                "year": int(year),
                                "month": int(month),
                                "day": int(day),
                                "date": _to_date(f"{year}-{month}-{day}"),
                                "name": item.get("name", "-"),
                                "service": item.get("service", "-"),
                                "status": item.get("status", "-"),
                                "price": _to_float(item.get("price")),
                                "price_display": _currency(_to_float(item.get("price"))),
                                "channel": item.get("canal", "-"),
                            }
                        )

    records.sort(key=lambda item: (item["date"] or date.min, item["city"], item["name"]))
    return records


def load_service_orders() -> list[dict[str, Any]]:
    orders_root = _as_dict(_branch("ordens_servico"))
    orders: list[dict[str, Any]] = []

    for city, city_data in orders_root.items():
        for year, year_data in _as_dict(city_data).items():
            for month, month_data in _as_dict(year_data).items():
                for day, day_data in _as_dict(month_data).items():
                    for order_id, order in _as_dict(day_data).items():
                        item = _as_dict(order)
                        orders.append(
                            {
                                "id": order_id,
                                "city": city,
                                "year": int(year),
                                "month": int(month),
                                "day": int(day),
                                "date": _to_date(f"{year}-{month}-{day}"),
                                "status_paymment": item.get("status_paymment", "aguardando"),
                                "service": item.get("service", "-"),
                                "newprice": _to_float(item.get("newprice")),
                                "tecnico_id": item.get("tecnico_id", ""),
                            }
                        )

    orders.sort(key=lambda item: (item["date"] or date.min, item["city"], item["service"]))
    return orders


def load_budget_entries(year: int, month: int) -> list[dict[str, Any]]:
    root = _as_dict(_branch("financeiro", "orcamentos", str(year), f"{month:02d}"))
    items: list[dict[str, Any]] = []

    for entry_id, entry in root.items():
        data = _as_dict(entry)
        items.append(
            {
                "id": entry_id,
                "category": data.get("category", "Sem categoria"),
                "planned_revenue": _to_float(data.get("planned_revenue")),
                "planned_expense": _to_float(data.get("planned_expense")),
                "notes": data.get("notes", ""),
                "planned_revenue_display": _currency(_to_float(data.get("planned_revenue"))),
                "planned_expense_display": _currency(_to_float(data.get("planned_expense"))),
            }
        )

    items.sort(key=lambda item: item["category"])
    return items


def save_budget_entry(year: int, month: int, category: str, planned_revenue: Any, planned_expense: Any, notes: str = "") -> tuple[bool, str]:
    clean_category = " ".join(str(category or "").split())
    if not clean_category:
        return False, "Informe uma categoria para o orcamento."

    slug = _slugify(clean_category)
    if not slug:
        return False, "Nao foi possivel gerar a chave da categoria."

    payload = {
        "category": clean_category,
        "planned_revenue": f"{_to_float(planned_revenue):.2f}",
        "planned_expense": f"{_to_float(planned_expense):.2f}",
        "notes": str(notes or "").strip(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    db.child("financeiro").child("orcamentos").child(str(year)).child(f"{month:02d}").child(slug).update(payload)
    return True, "Orcamento salvo com sucesso."


def get_available_years(reference_year: int | None = None) -> list[int]:
    years: set[int] = set()

    for transaction in load_manual_transactions():
        years.add(transaction["year"])

    for item in load_pending_os():
        years.add(item["year"])

    for item in load_confirmed_os():
        years.add(item["year"])

    for bucket in load_scheduled_transactions().values():
        for item in bucket:
            years.add(item["year"])

    if reference_year:
        years.add(reference_year)

    if not years:
        years.add(datetime.now().year)

    return sorted(years)


def build_system_notifications_context(reference_date: date | None = None) -> dict[str, Any]:
    today = reference_date or datetime.now().date()
    scheduled = load_scheduled_transactions()["pending"]

    overdue_items: list[dict[str, Any]] = []
    due_today_items: list[dict[str, Any]] = []
    upcoming_items: list[dict[str, Any]] = []

    for item in scheduled:
        due_date = item.get("due_date")
        if not due_date:
            continue

        days_until_due = (due_date - today).days
        kind_label = "Recebimento" if item.get("type") == "c" else "Pagamento"
        base_item = {
            "id": item.get("id"),
            "kind_label": kind_label,
            "description": item.get("description") or item.get("category") or kind_label,
            "category": item.get("category") or "Sem categoria",
            "destinatario": item.get("destinatario") or "-",
            "origem": item.get("origem") or "-",
            "amount": item.get("amount", 0.0),
            "amount_display": item.get("amount_display") or _currency(_to_float(item.get("amount"))),
            "due_date": due_date,
            "due_date_label": due_date.strftime("%d/%m/%Y"),
            "days_until_due": days_until_due,
            "link": "/lancamento_programado",
        }

        if days_until_due < 0:
            overdue_items.append(
                {
                    **base_item,
                    "status_key": "overdue",
                    "status_label": "Vencido",
                    "status_support": f"{abs(days_until_due)} dia(s) em atraso",
                    "severity_class": "negative",
                }
            )
        elif days_until_due == 0:
            due_today_items.append(
                {
                    **base_item,
                    "status_key": "today",
                    "status_label": "Vence hoje",
                    "status_support": "Baixa prevista para hoje",
                    "severity_class": "warning",
                }
            )
        elif days_until_due <= 3:
            upcoming_items.append(
                {
                    **base_item,
                    "status_key": "upcoming",
                    "status_label": "A vencer",
                    "status_support": f"Vence em {days_until_due} dia(s)",
                    "severity_class": "positive",
                }
            )

    overdue_items.sort(key=lambda item: item["due_date"])
    due_today_items.sort(key=lambda item: item["description"])
    upcoming_items.sort(key=lambda item: item["due_date"])

    highlighted = overdue_items + due_today_items + upcoming_items
    total_count = len(highlighted)

    return {
        "today_label": today.strftime("%d/%m/%Y"),
        "has_notifications": total_count > 0,
        "total_count": total_count,
        "overdue_count": len(overdue_items),
        "due_today_count": len(due_today_items),
        "upcoming_count": len(upcoming_items),
        "critical_count": len(overdue_items) + len(due_today_items),
        "overdue_items": overdue_items[:5],
        "due_today_items": due_today_items[:5],
        "upcoming_items": upcoming_items[:5],
        "highlighted_items": highlighted[:8],
    }


def _monthly_summary(transactions: list[dict[str, Any]], year: int, month: int) -> dict[str, Any]:
    monthly_items = [item for item in transactions if item["year"] == year and item["month"] == month]
    prior_items = [
        item
        for item in transactions
        if (item.get("year", 0), item.get("month", 0), item.get("day", 0), item.get("timestamp", 0)) < (year, month, 1, 0)
    ]

    opening_balance = sum(item["signed_amount"] for item in prior_items)
    receita = sum(item["amount"] for item in monthly_items if item["type"] == "c")
    despesas = sum(item["amount"] for item in monthly_items if item["type"] == "d")
    resultado = receita - despesas
    closing_balance = opening_balance + resultado

    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    category_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"label": "Sem categoria", "credit": 0.0, "debit": 0.0}
    )
    running_balance = opening_balance
    daily_rows = []

    for item in monthly_items:
        grouped_rows[f"{item['day']:02d}"].append(item)
        category_bucket = category_map[_category_key(item.get("category"))]
        category_bucket["label"] = _normalize_category_label(item.get("category"))
        if item["type"] == "c":
            category_bucket["credit"] += item["amount"]
        else:
            category_bucket["debit"] += item["amount"]

    for day_key in sorted(grouped_rows.keys(), key=int):
        entries = grouped_rows[day_key]
        inflow = sum(item["amount"] for item in entries if item["type"] == "c")
        outflow = sum(item["amount"] for item in entries if item["type"] == "d")
        opening_day = running_balance
        running_balance += inflow - outflow
        daily_rows.append(
            {
                "day": day_key,
                "date_label": f"{day_key}/{month:02d}/{year}",
                "opening_balance": opening_day,
                "opening_balance_display": _currency(opening_day),
                "inflow": inflow,
                "inflow_display": _currency(inflow),
                "outflow": outflow,
                "outflow_display": _currency(outflow),
                "closing_balance": running_balance,
                "closing_balance_display": _currency(running_balance),
                "transactions": entries,
            }
        )

    categories = []
    for _, values in sorted(category_map.items(), key=lambda item: item[1]["debit"] + item[1]["credit"], reverse=True):
        total = values["credit"] - values["debit"]
        categories.append(
            {
                "name": values["label"],
                "credit": values["credit"],
                "credit_display": _currency(values["credit"]),
                "debit": values["debit"],
                "debit_display": _currency(values["debit"]),
                "total": total,
                "total_display": _currency(total),
            }
        )

    return {
        "transactions": monthly_items,
        "grouped_rows": grouped_rows,
        "daily_rows": daily_rows,
        "opening_balance": opening_balance,
        "opening_balance_display": _currency(opening_balance),
        "receita": receita,
        "receita_display": _currency(receita),
        "despesas": despesas,
        "despesas_display": _currency(despesas),
        "resultado": resultado,
        "resultado_display": _currency(resultado),
        "closing_balance": closing_balance,
        "closing_balance_display": _currency(closing_balance),
        "transaction_count": len(monthly_items),
        "average_ticket": (receita / max(1, len([item for item in monthly_items if item["type"] == "c"]))),
        "average_ticket_display": _currency(receita / max(1, len([item for item in monthly_items if item["type"] == "c"]))),
        "categories": categories,
    }


def build_lancamentos_context(year: int, month: int) -> dict[str, Any]:
    transactions = load_manual_transactions()
    summary = _monthly_summary(transactions, year, month)
    years = get_available_years(reference_year=year)
    grouped = {}

    for row in summary["daily_rows"]:
        grouped[row["day"]] = {"transactions": {item["id"]: item for item in row["transactions"]}}

    return {
        "transactions": grouped,
        "daily_rows": summary["daily_rows"],
        "summary": summary,
        "ano": year,
        "mes": month,
        "meses": MONTH_NAMES,
        "anos": years,
        "caixa": _currency(_to_float(_branch("financeiro", "caixa"))),
        "destinatarios": list_destinatarios(),
    }


def build_dashboard_context(year: int, month: int) -> dict[str, Any]:
    today = datetime.now().date()
    all_transactions = load_manual_transactions()
    summary = _monthly_summary(all_transactions, year, month)
    pending_os = load_pending_os()
    confirmed_os = load_confirmed_os()
    scheduled = load_scheduled_transactions()

    monthly_trend = []
    for trend_year, trend_month in sorted({(item["year"], item["month"]) for item in all_transactions} | {(year, month)}):
        item_summary = _monthly_summary(all_transactions, trend_year, trend_month)
        monthly_trend.append(
            {
                "key": _month_key(trend_year, trend_month),
                "label": f"{MONTH_NAMES.get(trend_month, trend_month)}/{trend_year}",
                "receita": item_summary["receita"],
                "despesas": item_summary["despesas"],
                "resultado": item_summary["resultado"],
                "resultado_display": item_summary["resultado_display"],
            }
        )

    monthly_trend = monthly_trend[-6:]
    max_trend_value = max([abs(item["resultado"]) for item in monthly_trend] + [1.0])
    for item in monthly_trend:
        item["bar_size"] = max(8, int((abs(item["resultado"]) / max_trend_value) * 100))
        item["is_positive"] = item["resultado"] >= 0

    scheduled_pending = scheduled["pending"]
    upcoming_commitments = [item for item in scheduled_pending if item["due_date"] and item["due_date"] >= today]
    upcoming_commitments = upcoming_commitments[:8]

    overdue_commitments = [item for item in scheduled_pending if item["due_date"] and item["due_date"] < today]
    projected_inflow = sum(item["amount"] for item in scheduled_pending if item["type"] == "c")
    projected_outflow = sum(item["amount"] for item in scheduled_pending if item["type"] == "d")
    pending_receivable = sum(item["amount"] for item in pending_os)
    current_cash = _to_float(_branch("financeiro", "caixa"))
    projected_cash = current_cash + pending_receivable + projected_inflow - projected_outflow

    pending_by_technician: dict[str, dict[str, Any]] = defaultdict(lambda: {"tecnico": "-", "total": 0.0, "quantidade": 0})
    for item in pending_os:
        bucket = pending_by_technician[item["tecnico_id"] or item["tecnico"]]
        bucket["tecnico"] = item["tecnico"]
        bucket["total"] += item["amount"]
        bucket["quantidade"] += 1

    technicians_rank = sorted(pending_by_technician.values(), key=lambda item: item["total"], reverse=True)
    for technician in technicians_rank:
        technician["total_display"] = _currency(technician["total"])

    current_month_confirmed = [
        item for item in confirmed_os if item["year"] == year and item["month"] == month
    ]

    cities_count = len(_as_dict(_branch("cities")))
    services_count = len(_as_dict(_branch("services")))

    return {
        "ano": year,
        "mes": month,
        "month_name": MONTH_NAMES.get(month, str(month)),
        "meses": MONTH_NAMES,
        "anos": get_available_years(reference_year=year),
        "summary": summary,
        "saldo_atual_display": _currency(current_cash),
        "saldo_projetado_display": _currency(projected_cash),
        "receber_pendente_display": _currency(pending_receivable),
        "compromissos_futuros_display": _currency(projected_outflow),
        "compromissos_atrasados_display": _currency(sum(item["amount"] for item in overdue_commitments)),
        "confirmed_current_month_display": _currency(sum(item["amount"] for item in current_month_confirmed)),
        "pending_count": len(pending_os),
        "confirmed_current_month_count": len(current_month_confirmed),
        "monthly_trend": monthly_trend,
        "top_categories": summary["categories"][:6],
        "recent_transactions": list(reversed(summary["transactions"][-8:])),
        "upcoming_commitments": upcoming_commitments,
        "overdue_commitments": overdue_commitments[:8],
        "pending_by_technician": technicians_rank[:6],
        "city_count": cities_count,
        "service_count": services_count,
    }


def build_homepage_context(user_email: str) -> dict[str, Any]:
    today = datetime.now()
    dashboard = build_dashboard_context(today.year, today.month)
    return {
        "user_email": user_email,
        "summary": dashboard["summary"],
        "saldo_atual_display": dashboard["saldo_atual_display"],
        "saldo_projetado_display": dashboard["saldo_projetado_display"],
        "receber_pendente_display": dashboard["receber_pendente_display"],
        "pending_count": dashboard["pending_count"],
        "monthly_trend": dashboard["monthly_trend"][-4:],
    }


def build_cashflow_context(year: int, month: int) -> dict[str, Any]:
    dashboard = build_dashboard_context(year, month)
    summary = dashboard["summary"]
    scheduled = load_scheduled_transactions()
    pending_os = load_pending_os()

    projected_rows = []
    for item in scheduled["pending"]:
        due_date = item["due_date"]
        if due_date and due_date.year == year and due_date.month == month:
            projected_rows.append(
                {
                    "date_label": due_date.strftime("%d/%m/%Y"),
                    "kind": "Programado",
                    "description": item["description"] or item["category"],
                    "origin": item["origem"],
                    "destination": item["destinatario"],
                    "signed_amount": item["signed_amount"],
                    "signed_amount_display": _currency(item["signed_amount"]),
                    "is_positive": item["signed_amount"] >= 0,
                }
            )

    for item in pending_os:
        payment_date = item["date_payment"]
        if payment_date and payment_date.year == year and payment_date.month == month:
            projected_rows.append(
                {
                    "date_label": payment_date.strftime("%d/%m/%Y"),
                    "kind": "OS pendente",
                    "description": f"OS {item['numero_os']}",
                    "origin": item["tecnico"],
                    "destination": item["city_os"],
                    "signed_amount": item["amount"],
                    "signed_amount_display": _currency(item["amount"]),
                    "is_positive": True,
                }
            )

    projected_rows.sort(key=lambda item: datetime.strptime(item["date_label"], "%d/%m/%Y"))

    return {
        "ano": year,
        "mes": month,
        "month_name": MONTH_NAMES.get(month, str(month)),
        "meses": MONTH_NAMES,
        "anos": get_available_years(reference_year=year),
        "summary": summary,
        "projected_rows": projected_rows,
        "top_categories": dashboard["top_categories"],
        "pending_by_technician": dashboard["pending_by_technician"],
        "saldo_atual_display": dashboard["saldo_atual_display"],
        "saldo_projetado_display": dashboard["saldo_projetado_display"],
    }


def build_profit_analysis_context(year: int, month: int) -> dict[str, Any]:
    all_transactions = load_manual_transactions()
    summary = _monthly_summary(all_transactions, year, month)
    confirmed_os = load_confirmed_os()
    pending_os = load_pending_os()
    scheduled = load_scheduled_transactions()
    attendance_records = load_attendance_records()
    service_orders = load_service_orders()
    budgets = load_budget_entries(year, month)
    today = datetime.now().date()

    month_confirmed = [item for item in confirmed_os if item["year"] == year and item["month"] == month]
    historical_confirmed = [
        item for item in confirmed_os if (item["year"], item["month"]) < (year, month)
    ]

    gross_revenue = sum(item["valor_recebido"] for item in month_confirmed)
    technician_cost = sum(item["valor_tecnico"] for item in month_confirmed)
    fee_cost = sum(item["taxa"] + item["outros_custos_service"] for item in month_confirmed)
    company_margin = sum(item["valor_empresa"] for item in month_confirmed)
    other_revenues = sum(
        item["amount"]
        for item in summary["transactions"]
        if item["type"] == "c" and not _is_service_category(item.get("category"))
    )
    operating_expenses = sum(item["amount"] for item in summary["transactions"] if item["type"] == "d")
    operating_profit = summary["resultado"]
    margin_rate = _safe_divide(company_margin, gross_revenue)

    month_budgets_map = {_category_key(item["category"]): item for item in budgets}
    realized_category_map = {_category_key(item["name"]): item for item in summary["categories"]}
    category_names = sorted(set(month_budgets_map) | set(realized_category_map))
    budget_rows = []
    planned_revenue_total = 0.0
    planned_expense_total = 0.0
    realized_revenue_total = 0.0
    realized_expense_total = 0.0

    for category in category_names:
        budget = month_budgets_map.get(category, {})
        realized = realized_category_map.get(category, {})
        category_label = budget.get("category") or realized.get("name") or "Sem categoria"
        planned_revenue = float(budget.get("planned_revenue", 0.0))
        planned_expense = float(budget.get("planned_expense", 0.0))
        realized_revenue = float(realized.get("credit", 0.0))
        realized_expense = float(realized.get("debit", 0.0))

        planned_revenue_total += planned_revenue
        planned_expense_total += planned_expense
        realized_revenue_total += realized_revenue
        realized_expense_total += realized_expense

        budget_rows.append(
            {
                "category": category_label,
                "planned_revenue_display": _currency(planned_revenue),
                "realized_revenue_display": _currency(realized_revenue),
                "planned_expense_display": _currency(planned_expense),
                "realized_expense_display": _currency(realized_expense),
                "delta_revenue_display": _currency(realized_revenue - planned_revenue),
                "delta_expense_display": _currency(realized_expense - planned_expense),
                "planned_result_display": _currency(planned_revenue - planned_expense),
                "realized_result_display": _currency(realized_revenue - realized_expense),
                "notes": budget.get("notes", ""),
            }
        )

    totals_budget = {
        "planned_revenue_display": _currency(planned_revenue_total),
        "realized_revenue_display": _currency(realized_revenue_total),
        "planned_expense_display": _currency(planned_expense_total),
        "realized_expense_display": _currency(realized_expense_total),
        "planned_result_display": _currency(planned_revenue_total - planned_expense_total),
        "realized_result_display": _currency(realized_revenue_total - realized_expense_total),
        "delta_result_display": _currency((realized_revenue_total - realized_expense_total) - (planned_revenue_total - planned_expense_total)),
    }

    avg_margin_ratio = _safe_divide(
        sum(item["valor_empresa"] for item in historical_confirmed[-120:]),
        sum(item["valor_recebido"] for item in historical_confirmed[-120:]),
    )
    if avg_margin_ratio <= 0:
        avg_margin_ratio = margin_rate or 0.35

    history_start = date(max(today.year - 1, 2024), max(1, today.month - 3), 1)
    historical_attendances = [item for item in attendance_records if item["date"] and item["date"] >= history_start and item["date"] < today]
    historical_orders = [item for item in service_orders if item["date"] and item["date"] >= history_start and item["date"] < today]
    historical_close_rate = _safe_divide(len(historical_orders), len(historical_attendances))
    historical_close_rate = max(0.1, min(historical_close_rate or 0.45, 1.0))

    future_attendances = [
        item
        for item in attendance_records
        if item["date"] and item["date"] >= today and item["status"] in {"Agendado", "Aguardando"}
    ]

    windows = (30, 60, 90)
    future_projection = []
    for days in windows:
        limit = today.fromordinal(today.toordinal() + days)
        locked_profit = sum(item["valor_empresa"] for item in pending_os if item["date_payment"] and item["date_payment"] <= limit)
        scheduled_effect = sum(
            item["signed_amount"]
            for item in scheduled["pending"]
            if item["due_date"] and item["due_date"] <= limit
        )
        future_pipeline = [item for item in future_attendances if item["date"] <= limit]
        pipeline_gross = sum(item["price"] for item in future_pipeline)
        expected_pipeline_profit = pipeline_gross * historical_close_rate * avg_margin_ratio
        expected_profit = locked_profit + scheduled_effect + expected_pipeline_profit

        future_projection.append(
            {
                "label": f"Proximos {days} dias",
                "locked_profit_display": _currency(locked_profit + scheduled_effect),
                "expected_pipeline_profit_display": _currency(expected_pipeline_profit),
                "expected_profit_display": _currency(expected_profit),
                "expected_profit": expected_profit,
                "pipeline_count": len(future_pipeline),
            }
        )

    city_map: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "city": "-",
        "os_count": 0,
        "gross": 0.0,
        "company_margin": 0.0,
        "technician_cost": 0.0,
        "fees": 0.0,
    })
    technician_map: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "tecnico": "-",
        "os_count": 0,
        "gross": 0.0,
        "company_margin": 0.0,
        "technician_cost": 0.0,
    })

    for item in month_confirmed:
        city_bucket = city_map[item["city_os"]]
        city_bucket["city"] = item["city_os"]
        city_bucket["os_count"] += 1
        city_bucket["gross"] += item["valor_recebido"]
        city_bucket["company_margin"] += item["valor_empresa"]
        city_bucket["technician_cost"] += item["valor_tecnico"]
        city_bucket["fees"] += item["taxa"] + item["outros_custos_service"]

        tech_bucket = technician_map[item["tecnico_id"] or item["tecnico"]]
        tech_bucket["tecnico"] = item["tecnico"]
        tech_bucket["os_count"] += 1
        tech_bucket["gross"] += item["valor_recebido"]
        tech_bucket["company_margin"] += item["valor_empresa"]
        tech_bucket["technician_cost"] += item["valor_tecnico"]

    city_rows = []
    for row in sorted(city_map.values(), key=lambda item: item["company_margin"], reverse=True):
        row["gross_display"] = _currency(row["gross"])
        row["company_margin_display"] = _currency(row["company_margin"])
        row["technician_cost_display"] = _currency(row["technician_cost"])
        row["fees_display"] = _currency(row["fees"])
        row["margin_rate_display"] = f"{_safe_divide(row['company_margin'], row['gross']) * 100:.1f}%"
        city_rows.append(row)

    technician_rows = []
    for row in sorted(technician_map.values(), key=lambda item: item["company_margin"], reverse=True):
        row["gross_display"] = _currency(row["gross"])
        row["company_margin_display"] = _currency(row["company_margin"])
        row["technician_cost_display"] = _currency(row["technician_cost"])
        row["margin_rate_display"] = f"{_safe_divide(row['company_margin'], row['gross']) * 100:.1f}%"
        technician_rows.append(row)

    pipeline_by_city: dict[str, dict[str, Any]] = defaultdict(lambda: {"city": "-", "count": 0, "gross": 0.0})
    for item in future_attendances:
        bucket = pipeline_by_city[item["city"]]
        bucket["city"] = item["city"]
        bucket["count"] += 1
        bucket["gross"] += item["price"]

    pipeline_rows = []
    for row in sorted(pipeline_by_city.values(), key=lambda item: item["gross"], reverse=True)[:8]:
        row["gross_display"] = _currency(row["gross"])
        row["expected_profit_display"] = _currency(row["gross"] * historical_close_rate * avg_margin_ratio)
        pipeline_rows.append(row)

    return {
        "ano": year,
        "mes": month,
        "month_name": MONTH_NAMES.get(month, str(month)),
        "meses": MONTH_NAMES,
        "anos": get_available_years(reference_year=year),
        "summary": summary,
        "gross_revenue_display": _currency(gross_revenue),
        "technician_cost_display": _currency(technician_cost),
        "fee_cost_display": _currency(fee_cost),
        "company_margin_display": _currency(company_margin),
        "other_revenues_display": _currency(other_revenues),
        "operating_expenses_display": _currency(operating_expenses),
        "operating_profit_display": _currency(operating_profit),
        "margin_rate_display": f"{margin_rate * 100:.1f}%",
        "historical_close_rate_display": f"{historical_close_rate * 100:.1f}%",
        "avg_margin_ratio_display": f"{avg_margin_ratio * 100:.1f}%",
        "future_projection": future_projection,
        "budget_rows": budget_rows,
        "budget_totals": totals_budget,
        "budget_entries": budgets,
        "city_rows": city_rows[:10],
        "technician_rows": technician_rows[:10],
        "pipeline_rows": pipeline_rows,
        "future_attendance_count": len(future_attendances),
        "future_attendance_gross_display": _currency(sum(item["price"] for item in future_attendances)),
    }


def create_city(city_name: str) -> tuple[bool, str]:
    clean_name = " ".join(str(city_name or "").split())
    if not clean_name:
        return False, "Informe um nome de cidade valido."

    cities = _as_dict(_branch("cities"))
    normalized = {str(value).strip().lower() for value in cities.values()}
    if clean_name.lower() in normalized:
        return False, "Essa cidade ja esta cadastrada."

    db.child("cities").push(clean_name)
    return True, "Cidade cadastrada com sucesso."
