"""
Holy Laundry - Professional Laundry Management App
Built with Flet (https://flet.dev) - pure Python.

This version runs as a WEB APP (server-side), backed by a hosted Postgres
database via DATABASE_URL, so the same data is shared across every device
that opens the URL (iPhone, Android, desktop browser, etc.)

Run locally for testing:
    DATABASE_URL=postgres://... python main.py

Then open http://localhost:8000 in a browser.
"""

import datetime
import os
import flet as ft
import database as db
from collections import defaultdict

GARMENTS = ["Shirts", "Pants", "Dresses", "Bedding/Sheets", "Towels", "Jackets", "Delicates", "Other"]
SERVICES = ["Wash & Fold", "Dry Clean", "Wash & Iron", "Ironing Only", "Express (24h)"]
STAGES = ["Dropped Off", "Washing", "Ready", "Picked Up"]

TEAL = "#1F7A78"
TEAL_DARK = "#13524F"
TEAL_SOFT = "#E2F0EE"
CORAL = "#FF6B55"
CORAL_SOFT = "#FFE7E2"
AMBER_SOFT = "#FCEFDA"
GREEN_SOFT = "#E1F3E7"
INK = "#16292B"
MUTED = "#6F8688"
BG = "#EFF5F5"
LINE = "#E2EBEC"

STATUS_COLORS = {
    "Dropped Off": ("#9C6B17", AMBER_SOFT),
    "Washing": (TEAL_DARK, TEAL_SOFT),
    "Ready": ("#C8492F", CORAL_SOFT),
    "Picked Up": ("#1F7A41", GREEN_SOFT),
}


def today_str():
    return datetime.date.today().isoformat()


def fmt_date(d):
    if not d:
        return ""
    try:
        dt = datetime.date.fromisoformat(d)
        return dt.strftime("%b %d")
    except ValueError:
        return d


def next_status(status):
    i = STAGES.index(status)
    return STAGES[min(i + 1, len(STAGES) - 1)]


def main(page: ft.Page):
    page.title = "Holy Laundry"
    page.bgcolor = BG
    page.padding = 0
    page.fonts = {}

    # ---------------------------------------------------------------- state
    # Initialize state with fallback for database errors
try:
    clients = db.get_clients()
except Exception as e:
    clients = []
    print(f"Failed to load clients: {e}")

try:
    orders = db.get_orders()
except Exception as e:
    orders = []
    print(f"Failed to load orders: {e}")

try:
    inventory = db.get_inventory()
except Exception as e:
    inventory = []
    print(f"Failed to load inventory: {e}")

state = {
    "clients": clients,
    "orders": orders,
    "inventory": inventory,
        "tab": 0,
        "new_order": {
            "mode": "existing",
            "client_id": None,
            "new_name": "",
            "new_phone": "",
            "service": SERVICES[0],
            "items": [{"type": GARMENTS[0], "qty": 1}],
            "drop_off_date": today_str(),
            "due_date": "",
            "price": "",
            "notes": "",
        },
    }

    content_area = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    stats_row = ft.Row(spacing=10)
    header_sub = ft.Text("", color="white", size=13, weight=ft.FontWeight.W_500)

    def client_by_id(cid):
        return next((c for c in state["clients"] if c["id"] == cid), None)

    def refresh_data():
    try:
        state["clients"] = db.get_clients()
    except Exception as e:
        print(f"Failed to refresh clients: {e}")
    
    try:
        state["orders"] = db.get_orders()
    except Exception as e:
        print(f"Failed to refresh orders: {e}")
    
    try:
        state["inventory"] = db.get_inventory()
    except Exception as e:
        print(f"Failed to refresh inventory: {e}")

    def show_snack(msg):
        try:
            page.open(ft.SnackBar(content=ft.Text(msg), duration=1600))
        except Exception:
            try:
                page.show_dialog(ft.SnackBar(content=ft.Text(msg), duration=1600))
            except Exception:
                pass

    # ----------------------------------------------------------- nav / tabs
    def on_nav_change(e):
        state["tab"] = e.control.selected_index
        render()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_ROUNDED, label="Dashboard"),
            ft.NavigationBarDestination(icon=ft.Icons.ADD_CIRCLE_ROUNDED, label="New Order"),
            ft.NavigationBarDestination(icon=ft.Icons.PEOPLE_ROUNDED, label="Clients"),
            ft.NavigationBarDestination(icon=ft.Icons.INVENTORY_2_ROUNDED, label="Inventory"),
            ft.NavigationBarDestination(icon=ft.Icons.ANALYTICS_ROUNDED, label="Reports"),
        ],
    )
    page.navigation_bar = nav_bar

    # --------------------------------------------------------------- stats
    def stat_pill(num, label):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(str(num), size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text(label.upper(), size=10, color="white", weight=ft.FontWeight.W_600),
                ],
                spacing=2,
            ),
            bgcolor="#33FFFFFF",
            border_radius=14,
            padding=ft.Padding(12, 10, 12, 10),
            expand=True,
        )

    def render_stats():
        active = sum(1 for o in state["orders"] if o["status"] != "Picked Up")
        ready = sum(1 for o in state["orders"] if o["status"] == "Ready")
        low = sum(1 for i in state["inventory"] if i["qty"] <= i["reorder"])
        stats_row.controls = [
            stat_pill(active, "Active"),
            stat_pill(ready, "Ready"),
            stat_pill(low, "Low stock"),
        ]

    # ------------------------------------------------------------- dialogs
    def open_order_detail(order):
        client = client_by_id(order["client_id"])
        status_buttons = []
        for s in STAGES:
            is_on = s == order["status"]
            status_buttons.append(
                ft.Container(
                    content=ft.Text(s, size=12, weight=ft.FontWeight.BOLD,
                                     color="white" if is_on else MUTED),
                    bgcolor=TEAL if is_on else BG,
                    border_radius=9,
                    padding=ft.Padding(0, 9, 0, 9),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                    on_click=lambda e, st=s: set_status_and_close(order["id"], st),
                )
            )

        items_text = "\n".join(f"{i['qty']:g}x {i['type']}" for i in order["items"])
        dlg = ft.AlertDialog(
            title=ft.Text("Order detail"),
            content=ft.Column(
                [
                    ft.Text(f"{client['name'] if client else 'Unknown'} - {order['service']}", color=MUTED, size=12),
                    ft.Divider(),
                    ft.Text("STATUS", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                    ft.Row(status_buttons, spacing=6),
                    ft.Text("ITEMS", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                    ft.Text(items_text, size=13),
                    ft.Text("DROP-OFF / DUE", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                    ft.Text(f"{fmt_date(order['drop_off_date'])}"
                            + (f" -> {fmt_date(order['due_date'])}" if order.get("due_date") else ""), size=13),
                    ft.Text("PRICE", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                    ft.Text(f"${float(order['price']):.2f}" if order.get("price") else "Not set", size=13),
                ],
                spacing=8,
                tight=True,
            ),
            actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
        )
        page.show_dialog(dlg)

    def set_status_and_close(order_id, status):
        db.update_order_status(order_id, status)
        page.pop_dialog()
        refresh_data()
        render()
        show_snack(f"Order marked {status}")

    def advance_order(e, order_id):
        order = next(o for o in state["orders"] if o["id"] == order_id)
        new_status = next_status(order["status"])
        db.update_order_status(order_id, new_status)
        refresh_data()
        render()
        show_snack(f"Order marked {new_status}")

    # ------------------------------------------------------------ dashboard
    def order_card(order):
        client = client_by_id(order["client_id"])
        fg, bgc = STATUS_COLORS.get(order["status"], STATUS_COLORS["Dropped Off"])
        total_items = sum(i["qty"] for i in order["items"])
        chips = ft.Row(
            [
                ft.Container(
                    content=ft.Text(f"{i['qty']:g}x {i['type']}", size=11, color=MUTED, weight=ft.FontWeight.W_600),
                    bgcolor=BG, border=ft.Border.all(1, LINE), border_radius=8,
                    padding=ft.Padding(8, 3, 8, 3),
                )
                for i in order["items"][:4]
            ],
            wrap=True, spacing=6,
        )
        bottom_right = (
            ft.ElevatedButton(
                f"Mark {next_status(order['status'])}",
                bgcolor=CORAL, color="white",
                on_click=lambda e: advance_order(e, order["id"]),
            )
            if order["status"] != "Picked Up"
            else ft.Text("Completed", size=12, color=MUTED)
        )
        card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(client["name"] if client else "Unknown client",
                                             weight=ft.FontWeight.BOLD, size=14.5),
                                    ft.Text(
                                        f"{total_items:g} item(s) - Dropped {fmt_date(order['drop_off_date'])}"
                                        + (f" - Due {fmt_date(order['due_date'])}" if order.get("due_date") else ""),
                                        size=12, color=MUTED,
                                    ),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(order["status"], size=11, weight=ft.FontWeight.BOLD, color=fg),
                                bgcolor=bgc, border_radius=999, padding=ft.Padding(10, 4, 10, 4),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    chips,
                    ft.Row(
                        [
                            ft.Text(f"${float(order['price']):.2f}" if order.get("price") else "-",
                                     weight=ft.FontWeight.BOLD, size=15),
                            bottom_right,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
            bgcolor="white", border=ft.Border.all(1, LINE), border_radius=16,
            padding=14,
            on_click=lambda e: open_order_detail(order),
        )
        return card

    def build_dashboard():
        if not state["orders"]:
            return [empty_state(ft.Icons.LOCAL_LAUNDRY_SERVICE_ROUNDED, "No orders yet",
                                 "Tap New Order below to log your first laundry intake.")]
        sorted_orders = sorted(state["orders"], key=lambda o: (o["status"] == "Picked Up", -o["created_at"]))
        return [section_title("Orders")] + [order_card(o) for o in sorted_orders]

    def empty_state(icon, title, desc):
        return ft.Column(
            [
                ft.Icon(icon, size=40, color=MUTED),
                ft.Text(title, weight=ft.FontWeight.BOLD, size=15),
                ft.Text(desc, size=12.5, color=MUTED, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6,
        )

    def section_title(text, trailing=None):
        row = [ft.Text(text, size=17, weight=ft.FontWeight.BOLD)]
        if trailing:
            row.append(trailing)
        return ft.Row(row, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # ------------------------------------------------------------ new order
    def build_new_order():
        d = state["new_order"]

        def set_mode(mode):
            d["mode"] = mode
            render()

        seg = ft.Row(
            [
                ft.Container(
                    content=ft.Text("Existing", size=12.5, weight=ft.FontWeight.BOLD,
                                     color="white" if d["mode"] == "existing" else MUTED),
                    bgcolor=TEAL if d["mode"] == "existing" else BG, border_radius=9,
                    padding=ft.Padding(0, 9, 0, 9), alignment=ft.Alignment.CENTER, expand=True,
                    on_click=lambda e: set_mode("existing"),
                ),
                ft.Container(
                    content=ft.Text("New client", size=12.5, weight=ft.FontWeight.BOLD,
                                     color="white" if d["mode"] == "new" else MUTED),
                    bgcolor=TEAL if d["mode"] == "new" else BG, border_radius=9,
                    padding=ft.Padding(0, 9, 0, 9), alignment=ft.Alignment.CENTER, expand=True,
                    on_click=lambda e: set_mode("new"),
                ),
            ],
            spacing=4,
        )

        if d["mode"] == "existing":
            def on_client_select(e):
                d["client_id"] = e.control.value

            client_field = ft.Dropdown(
                label="Select a client",
                value=d["client_id"],
                options=[ft.DropdownOption(key=c["id"], text=c["name"]) for c in state["clients"]],
                on_select=on_client_select,
            )
            client_controls = [client_field]
        else:
            def on_name_change(e):
                d["new_name"] = e.control.value

            def on_phone_change(e):
                d["new_phone"] = e.control.value

            client_controls = [
                ft.TextField(label="Full name", value=d["new_name"], on_change=on_name_change),
                ft.TextField(label="Phone number", value=d["new_phone"], on_change=on_phone_change),
            ]

        def on_service_select(e):
            d["service"] = e.control.value

        service_field = ft.Dropdown(
            label="Service type", value=d["service"],
            options=[ft.DropdownOption(key=s, text=s) for s in SERVICES],
            on_select=on_service_select,
        )

        # ---- item rows ----
        def on_item_type_select(e, idx):
            d["items"][idx]["type"] = e.control.value

        def on_item_qty_change(e, idx):
            d["items"][idx]["qty"] = e.control.value

        def remove_item(e, idx):
            d["items"].pop(idx)
            render()

        def add_item(e):
            d["items"].append({"type": GARMENTS[0], "qty": 1})
            render()

        item_rows = []
        for idx, it in enumerate(d["items"]):
            row_controls = [
                ft.Dropdown(
                    value=it["type"], expand=2,
                    options=[ft.DropdownOption(key=g, text=g) for g in GARMENTS],
                    on_select=lambda e, i=idx: on_item_type_select(e, i),
                ),
                ft.TextField(value=str(it["qty"]), expand=1, keyboard_type=ft.KeyboardType.NUMBER,
                             on_change=lambda e, i=idx: on_item_qty_change(e, i)),
            ]
            if len(d["items"]) > 1:
                row_controls.append(
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_color=CORAL,
                                  on_click=lambda e, i=idx: remove_item(e, i))
                )
            item_rows.append(ft.Row(row_controls, spacing=8))

        def on_dropoff_change(e):
            d["drop_off_date"] = e.control.value

        def on_due_change(e):
            d["due_date"] = e.control.value

        def on_price_change(e):
            d["price"] = e.control.value

        def on_notes_change(e):
            d["notes"] = e.control.value

        return [
            section_title("New Order"),
            ft.Text("CLIENT", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            seg,
            *client_controls,
            ft.Text("SERVICE TYPE", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            service_field,
            ft.Text("ITEMS", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            *item_rows,
            ft.TextButton("+ Add another item type", on_click=add_item),
            ft.Text("DROP-OFF DATE", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.TextField(value=d["drop_off_date"], hint_text="YYYY-MM-DD", on_change=on_dropoff_change),
            ft.Text("DUE / READY DATE", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.TextField(value=d["due_date"], hint_text="YYYY-MM-DD", on_change=on_due_change),
            ft.Text("PRICE ($)", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.TextField(value=d["price"], hint_text="0.00", keyboard_type=ft.KeyboardType.NUMBER,
                         on_change=on_price_change),
            ft.Text("NOTES", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.TextField(value=d["notes"], multiline=True, min_lines=2, max_lines=4, on_change=on_notes_change),
            ft.ElevatedButton(
                "Save order & update dashboard", bgcolor=TEAL, color="white", width=400,
                on_click=lambda e: save_new_order(),
            ),
        ]

    def save_new_order():
        d = state["new_order"]
        client_id = d["client_id"]
        if d["mode"] == "new":
            if not d["new_name"].strip():
                show_snack("Enter a client name")
                return
            c = db.add_client(d["new_name"].strip(), d["new_phone"].strip())
            client_id = c["id"]
        if not client_id:
            show_snack("Select or add a client")
            return
        items = [{"type": i["type"], "qty": float(i["qty"] or 0)} for i in d["items"] if float(i["qty"] or 0) > 0]
        if not items:
            show_snack("Add at least one item")
            return
        db.add_order(client_id, d["service"], items, d["drop_off_date"], d["due_date"], d["price"], d["notes"])
        state["new_order"] = {
            "mode": "existing", "client_id": None, "new_name": "", "new_phone": "",
            "service": SERVICES[0], "items": [{"type": GARMENTS[0], "qty": 1}],
            "drop_off_date": today_str(), "due_date": "", "price": "", "notes": "",
        }
        refresh_data()
        state["tab"] = 0
        nav_bar.selected_index = 0
        render()
        show_snack("Order saved")

    # -------------------------------------------------------------- clients
    def open_add_client_dialog():
        name_field = ft.TextField(label="Full name")
        phone_field = ft.TextField(label="Phone")
        address_field = ft.TextField(label="Address (optional)")

        def save(e):
            if not name_field.value or not name_field.value.strip():
                show_snack("Enter a name")
                return
            db.add_client(name_field.value.strip(), phone_field.value or "", address_field.value or "")
            page.pop_dialog()
            refresh_data()
            render()
            show_snack("Client added")

        dlg = ft.AlertDialog(
            title=ft.Text("Add client"),
            content=ft.Column([name_field, phone_field, address_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                ft.ElevatedButton("Save", bgcolor=TEAL, color="white", on_click=save),
            ],
        )
        page.show_dialog(dlg)

    def open_client_detail(client):
        c_orders = [o for o in state["orders"] if o["client_id"] == client["id"]]
        c_orders.sort(key=lambda o: -o["created_at"])
        order_summaries = [
            ft.Text(
                f"{o['status']} - {sum(i['qty'] for i in o['items']):g} item(s) - {fmt_date(o['drop_off_date'])}",
                size=12.5,
            )
            for o in c_orders
        ] or [ft.Text("No orders yet for this client.", size=12.5, color=MUTED)]

        dlg = ft.AlertDialog(
            title=ft.Text(client["name"]),
            content=ft.Column(
                [
                    ft.Text(f"{client.get('phone') or 'No phone'}"
                            + (f" - {client['address']}" if client.get("address") else ""), color=MUTED, size=12),
                    ft.Divider(),
                    ft.Text("ORDER HISTORY", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                    *order_summaries,
                ],
                tight=True, spacing=8,
            ),
            actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
        )
        page.show_dialog(dlg)

    def build_clients():
        if not state["clients"]:
            body = [empty_state(ft.Icons.PERSON_ROUNDED, "No clients yet",
                                 "Add your first client to start logging orders.")]
        else:
            rows = []
            for c in state["clients"]:
                order_count = sum(1 for o in state["orders"] if o["client_id"] == c["id"])
                initials = "".join(p[0].upper() for p in c["name"].split()[:2])
                rows.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.CircleAvatar(content=ft.Text(initials, color=TEAL_DARK, weight=ft.FontWeight.BOLD),
                                                bgcolor=TEAL_SOFT, radius=19),
                                ft.Column(
                                    [
                                        ft.Text(c["name"], weight=ft.FontWeight.BOLD, size=14),
                                        ft.Text(f"{c.get('phone') or 'No phone'} - {order_count} order(s)",
                                                 size=12, color=MUTED),
                                    ],
                                    spacing=1, expand=True,
                                ),
                                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=MUTED),
                            ],
                            spacing=10,
                        ),
                        padding=ft.Padding(0, 10, 0, 10),
                        on_click=lambda e, cl=c: open_client_detail(cl),
                    )
                )
            body = [
                ft.Container(
                    content=ft.Column(rows, spacing=0),
                    bgcolor="white", border=ft.Border.all(1, LINE), border_radius=16, padding=14,
                )
            ]
        add_btn = ft.OutlinedButton("+ Add client", on_click=lambda e: open_add_client_dialog())
        return [section_title("Clients", trailing=add_btn)] + body

    # ------------------------------------------------------------ inventory
    def open_add_inventory_dialog():
        name_field = ft.TextField(label="Item name")
        qty_field = ft.TextField(label="Starting quantity", value="0", keyboard_type=ft.KeyboardType.NUMBER)
        unit_field = ft.TextField(label="Unit (e.g. boxes, L, pcs)")
        reorder_field = ft.TextField(label="Reorder threshold", value="5", keyboard_type=ft.KeyboardType.NUMBER)

        def save(e):
            if not name_field.value or not name_field.value.strip():
                show_snack("Enter an item name")
                return
            db.add_inventory_item(
                name_field.value.strip(),
                float(qty_field.value or 0),
                unit_field.value.strip() or "pcs",
                float(reorder_field.value or 0),
            )
            page.pop_dialog()
            refresh_data()
            render()
            show_snack("Item added")

        dlg = ft.AlertDialog(
            title=ft.Text("Add inventory item"),
            content=ft.Column([name_field, qty_field, unit_field, reorder_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                ft.ElevatedButton("Save", bgcolor=TEAL, color="white", on_click=save),
            ],
        )
        page.show_dialog(dlg)

    def adjust_inventory(e, item_id, delta):
        item = next(i for i in state["inventory"] if i["id"] == item_id)
        new_qty = max(0, item["qty"] + delta)
        db.set_inventory_qty(item_id, new_qty)
        refresh_data()
        render()

    def build_inventory():
        rows = []
        for i in state["inventory"]:
            low = i["qty"] <= i["reorder"]
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(i["name"], weight=ft.FontWeight.BOLD, size=14),
                                            ft.Container(
                                                content=ft.Text("LOW", size=10, weight=ft.FontWeight.BOLD,
                                                                 color="#C8492F"),
                                                bgcolor=CORAL_SOFT, border_radius=6, padding=ft.Padding(6, 1, 6, 1),
                                                visible=low,
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Text(f"{i['qty']:g} {i['unit']} on hand - reorder at {i['reorder']:g}",
                                             size=12, color=MUTED),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(icon=ft.Icons.REMOVE, icon_size=16,
                                                  on_click=lambda e, iid=i["id"]: adjust_inventory(e, iid, -1)),
                                    ft.Text(f"{i['qty']:g}", weight=ft.FontWeight.BOLD, size=14),
                                    ft.IconButton(icon=ft.Icons.ADD, icon_size=16,
                                                  on_click=lambda e, iid=i["id"]: adjust_inventory(e, iid, 1)),
                                ],
                                spacing=2,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding(0, 10, 0, 10),
                )
            )
        add_btn = ft.OutlinedButton("+ Add item", on_click=lambda e: open_add_inventory_dialog())
        return [
            section_title("Inventory", trailing=add_btn),
            ft.Container(
                content=ft.Column(rows, spacing=0),
                bgcolor="white", border=ft.Border.all(1, LINE), border_radius=16, padding=14,
            ),
            ft.Text("Stock updates instantly for everyone on the team.", size=11, color=MUTED,
                     text_align=ft.TextAlign.CENTER),
        ]

    # ------------------------------------------------------------ reports
    def build_reports():
        """Build comprehensive reports: customers per day, revenue, inventory status."""

        orders_by_date = defaultdict(lambda: {"count": 0, "revenue": 0, "orders": []})
        for order in state["orders"]:
            date = order["drop_off_date"]
            orders_by_date[date]["count"] += 1
            orders_by_date[date]["revenue"] += float(order["price"] or 0)
            orders_by_date[date]["orders"].append(order)

        sorted_dates = sorted(orders_by_date.keys(), reverse=True)

        customers_rows = []
        for date in sorted_dates[:14]:
            data = orders_by_date[date]
            date_obj = datetime.date.fromisoformat(date)
            customers_rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column([
                                ft.Text(date_obj.strftime("%a, %b %d"), weight=ft.FontWeight.BOLD, size=13),
                                ft.Text(date, size=11, color=MUTED),
                            ], spacing=1, expand=True),
                            ft.Container(
                                content=ft.Text(f"{data['count']}", size=16, weight=ft.FontWeight.BOLD, color="white"),
                                bgcolor=TEAL, border_radius=8, padding=ft.Padding(12, 8, 12, 8),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding(0, 8, 0, 8),
                )
            )

        revenue_rows = []
        for date in sorted_dates[:14]:
            data = orders_by_date[date]
            date_obj = datetime.date.fromisoformat(date)
            revenue_rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column([
                                ft.Text(date_obj.strftime("%a, %b %d"), weight=ft.FontWeight.BOLD, size=13),
                                ft.Text(date, size=11, color=MUTED),
                            ], spacing=1, expand=True),
                            ft.Container(
                                content=ft.Text(f"${data['revenue']:.2f}", size=16, weight=ft.FontWeight.BOLD, color="white"),
                                bgcolor=CORAL, border_radius=8, padding=ft.Padding(12, 8, 12, 8),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding(0, 8, 0, 8),
                )
            )

        low_stock = [i for i in state["inventory"] if i["qty"] <= i["reorder"]]
        ok_stock = [i for i in state["inventory"] if i["qty"] > i["reorder"]]

        inventory_rows = []
        if low_stock:
            inventory_rows.append(ft.Text("⚠ LOW STOCK ITEMS", size=12, weight=ft.FontWeight.BOLD, color=CORAL))
            for item in low_stock:
                inventory_rows.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(item["name"], weight=ft.FontWeight.BOLD, size=13),
                                ft.Text(f"Threshold: {item['reorder']:g}", size=11, color=MUTED),
                            ], spacing=1, expand=True),
                            ft.Container(
                                content=ft.Text(f"{item['qty']:g} {item['unit']}", size=13, weight=ft.FontWeight.BOLD, color="white"),
                                bgcolor=CORAL, border_radius=8, padding=ft.Padding(10, 6, 10, 6),
                            ),
                        ]),
                        padding=ft.Padding(0, 8, 0, 8),
                    )
                )

        if ok_stock:
            inventory_rows.append(ft.Text("✓ HEALTHY STOCK", size=12, weight=ft.FontWeight.BOLD, color=MUTED))
            for item in ok_stock[:8]:
                inventory_rows.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(item["name"], weight=ft.FontWeight.BOLD, size=13),
                                ft.Text(f"Threshold: {item['reorder']:g}", size=11, color=MUTED),
                            ], spacing=1, expand=True),
                            ft.Container(
                                content=ft.Text(f"{item['qty']:g} {item['unit']}", size=13, weight=ft.FontWeight.BOLD, color="white"),
                                bgcolor="#1F7A41", border_radius=8, padding=ft.Padding(10, 6, 10, 6),
                            ),
                        ]),
                        padding=ft.Padding(0, 8, 0, 8),
                    )
                )

        total_customers = sum(1 for o in state["orders"])
        total_revenue = sum(float(o["price"] or 0) for o in state["orders"])

        return [
            section_title("Reports"),
            ft.Container(
                content=ft.Column([
                    ft.Text("Total Customers (All Time)", size=13, weight=ft.FontWeight.W_600, color=MUTED),
                    ft.Text(f"{total_customers}", size=32, weight=ft.FontWeight.BOLD, color=TEAL),
                ], spacing=4),
                bgcolor="white", border=ft.Border.all(1, LINE), border_radius=12, padding=14,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Total Revenue (All Time)", size=13, weight=ft.FontWeight.W_600, color=MUTED),
                    ft.Text(f"${total_revenue:.2f}", size=32, weight=ft.FontWeight.BOLD, color=CORAL),
                ], spacing=4),
                bgcolor="white", border=ft.Border.all(1, LINE), border_radius=12, padding=14,
            ),
            ft.Divider(height=1),
            ft.Text("CUSTOMERS PER DAY (Last 14 days)", size=12, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.Container(
                content=ft.Column(customers_rows or [ft.Text("No data", color=MUTED)], spacing=0),
                bgcolor="white", border=ft.Border.all(1, LINE), border_radius=12, padding=12,
            ),
            ft.Divider(height=1),
            ft.Text("REVENUE PER DAY (Last 14 days)", size=12, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.Container(
                content=ft.Column(revenue_rows or [ft.Text("No data", color=MUTED)], spacing=0),
                bgcolor="white", border=ft.Border.all(1, LINE), border_radius=12, padding=12,
            ),
            ft.Divider(height=1),
            ft.Text("INVENTORY STATUS", size=12, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.Container(
                content=ft.Column(inventory_rows or [ft.Text("No inventory items", color=MUTED)], spacing=4),
                bgcolor="white", border=ft.Border.all(1, LINE), border_radius=12, padding=12,
            ),
        ]

    # ----------------------------------------------------------------- root
    def render():
        render_stats()
        builders = [build_dashboard, build_new_order, build_clients, build_inventory, build_reports]
        content_area.controls = builders[state["tab"]]()
        header_sub.value = datetime.date.today().strftime("%A, %B %d")
        page.update()

    header = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCAL_LAUNDRY_SERVICE_ROUNDED, color="white", size=22),
                        ft.Text("Holy Laundry", size=20, weight=ft.FontWeight.BOLD, color="white"),
                    ],
                    spacing=8,
                ),
                header_sub,
                stats_row,
            ],
            spacing=4,
        ),
        bgcolor=TEAL,
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                    colors=[TEAL, TEAL_DARK]),
        padding=ft.Padding(20, 20, 20, 22),
    )

    page.add(
        ft.Column(
            [header, ft.Container(content=content_area, padding=16, expand=True)],
            spacing=0, expand=True,
        )
    )

    render()


if __name__ == "__main__":
    # Web mode: listens on 0.0.0.0 so the hosting platform can route traffic in,
    # and reads the port from the PORT env var the platform provides.
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
