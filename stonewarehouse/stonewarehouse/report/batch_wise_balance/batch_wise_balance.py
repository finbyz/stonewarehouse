# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe, datetime
from frappe import _
from frappe.utils import cint, flt, getdate, get_url_to_form

def execute(filters=None):
	if not filters: filters = {}

	float_precision = cint(frappe.db.get_default("float_precision")) or 3

	columns = get_columns(filters)
	item_pick_map = get_picked_qty(filters,float_precision)
	iwb_map = get_item_warehouse_batch_map(filters, float_precision)
	conditions = ''
	if filters.get("to_date"):
		conditions += " AND pl.posting_date <= '%s'" % filters["to_date"]
	
	data = []
	if filters.get('warehouse'):
		for item in sorted(iwb_map):
			if not filters.get("item") or filters.get("item") == item:
				for wh in sorted(iwb_map[item]):
					for batch in sorted(iwb_map[item][wh]):
						qty_dict = iwb_map[item][wh][batch]
						try:
							picked_qty = item_pick_map[item][batch].pickedqty
							unlocked_qty = item_pick_map[item][batch].unlocked_qty
						except KeyError:
							picked_qty = 0.0
							unlocked_qty = 0.0
						# frappe.db.sql(f"""
						# SELECT sum(pli.qty - (pli.wastage_qty + pli.delivered_qty)) FROM `tabPick List Item` as pli JOIN `tabPick List` as pl on pli.parent = pl.name 
						# WHERE pli.item_code = '{item}' AND pli.batch_no='{batch}' and pl.docstatus = 1 {conditions} AND pl.company = '{filters.get('company')}'
						# """)[0][0] or 0.0
						detail_button = """
							<button style='margin-left:5px;border:none;color: #fff; background-color: #5e64ff; padding: 3px 5px;border-radius: 5px;' 
								type='button' item-code='{}' batch-no='{}' company='{}' from-date='{}' to-date='{}' bal-qty='{}', total-picked-qty = '{}' total-remaining-qty='{}'
								onClick='get_picked_item_details(this.getAttribute("item-code"), this.getAttribute("batch-no"), this.getAttribute("company"), this.getAttribute("from-date"), this.getAttribute("to-date"), this.getAttribute("bal-qty"), this.getAttribute("total-picked-qty"), this.getAttribute("total-remaining-qty"))'>View</button>""".format(item, batch, filters.get('company'), filters.get('from_date'), filters.get('to_date'), flt(qty_dict.bal_qty, float_precision), picked_qty, flt(qty_dict.bal_qty, float_precision) - picked_qty)
						# # frappe.throw(str(detail_button))
						if qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty:
							if filters.get('sales_order'):
								so_picked_qty = frappe.db.get_value("Pick List Item", {'sales_order': filters.sales_order, 'item_code': item, 'batch_no': batch}, 'sum(qty - delivered_qty - wastage_qty)') or 0.0
							else:
								so_picked_qty = 0.0
							data.append({
								'item_code': item,
								'balance_qty': flt(qty_dict.bal_qty, float_precision),
								'picked_qty': picked_qty,
								'unlocked_qty': unlocked_qty + (flt(qty_dict.bal_qty, float_precision) - picked_qty),
								'remaining_qty': flt(qty_dict.bal_qty, float_precision) - picked_qty,
								'picked_detail': detail_button,
								'opening_qty': flt(qty_dict.opening_qty, float_precision),
								'in_qty': flt(qty_dict.in_qty, float_precision),
								'out_qty': flt(qty_dict.out_qty, float_precision), 
								'batch_no': batch,
								'item_group': qty_dict.item_group,
								'image': qty_dict.image,
								'so_picked_qty': so_picked_qty,
								'warehouse': wh,
								'company': frappe.db.get_value("Warehouse",wh,"company")
							})
	else:
		for item in iwb_map:
			if not filters.get("item") or filters.get("item") == item:
				for batch in sorted(iwb_map[item]):
					qty_dict = iwb_map[item][batch]
					try:
						picked_qty = item_pick_map[item][batch].pickedqty
						unlocked_qty = item_pick_map[item][batch].unlocked_qty
					except KeyError:
						picked_qty = 0.0
						unlocked_qty = 0.0
					# frappe.db.sql(f"""
					# SELECT sum(pli.qty - (pli.wastage_qty + pli.delivered_qty)) FROM `tabPick List Item` as pli JOIN `tabPick List` as pl on pli.parent = pl.name 
					# WHERE pli.item_code = '{item}' AND pli.batch_no='{batch}' and pl.docstatus = 1 {conditions} AND pl.company = '{filters.get('company')}'
					# """)[0][0] or 0.0
					detail_button = """
						<button style='margin-left:5px;border:none;color: #fff; background-color: #5e64ff; padding: 3px 5px;border-radius: 5px;' 
							type='button' item-code='{}' batch-no='{}' company='{}' from-date='{}' to-date='{}' bal-qty='{}', total-picked-qty = '{}' total-remaining-qty='{}'
							onClick='get_picked_item_details(this.getAttribute("item-code"), this.getAttribute("batch-no"), this.getAttribute("company"), this.getAttribute("from-date"), this.getAttribute("to-date"), this.getAttribute("bal-qty"), this.getAttribute("total-picked-qty"), this.getAttribute("total-remaining-qty"))'>View</button>""".format(item, batch, filters.get('company'), filters.get('from_date'), filters.get('to_date'), flt(qty_dict.bal_qty, float_precision), picked_qty, flt(qty_dict.bal_qty, float_precision) - picked_qty)
					# # frappe.throw(str(detail_button))
					if qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty:
						if filters.get('sales_order'):
							so_picked_qty = frappe.db.get_value("Pick List Item", {'sales_order': filters.sales_order, 'item_code': item, 'batch_no': batch}, 'sum(qty - delivered_qty - wastage_qty)') or 0.0
						else:
							so_picked_qty = 0.0
						data.append({
							'item_code': item,
							'balance_qty': flt(qty_dict.bal_qty, float_precision),
							'picked_qty': picked_qty,
							'unlocked_qty': unlocked_qty + (flt(qty_dict.bal_qty, float_precision) - picked_qty),
							'remaining_qty': flt(qty_dict.bal_qty, float_precision) - picked_qty,
							'picked_detail': detail_button,
							'opening_qty': flt(qty_dict.opening_qty, float_precision),
							'in_qty': flt(qty_dict.in_qty, float_precision),
							'out_qty': flt(qty_dict.out_qty, float_precision), 
							'batch_no': batch,
							'item_group': qty_dict.item_group,
							'image': qty_dict.image,
							'so_picked_qty': so_picked_qty
						})


	return columns, data

def get_columns(filters):
	"""return columns based on filters"""

	columns = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "link",
			"options": "Item",
			"width": 250
		},	
		{
			"label": _("Balance Qty"),
			"fieldname": "balance_qty",
			"fieldtype": "Float",
			"width": 80
		},
		{
			"label": _("Unlocked Qty"),
			"fieldname": "unlocked_qty",
			"fieldtype": "Float",
			"width": 80
		},
		
		
	]
	if not filters.get('warehouse'):
		columns += [
			{
				"label": _("Picked Qty"),
				"fieldname": "picked_qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("Remaining Qty"),
				"fieldname": "remaining_qty",
				"fieldtype": "Float",
				"width": 80
			},
			{
				"label": _("Details"),
				"fieldname": "picked_detail",
				"fieldtype": "Data",
				"width": 70
			},
		]
		
	if filters.get('sales_order'):
		columns += [
		{
			"label": _("Sales Order Picked Qty"),
			"fieldname": "so_picked_qty",
			"fieldtype": "Float",
			"width": 70,
			"default": 0
		}
	]

	columns += [
		{
			"label": _("Batch"),
			"fieldname": "batch_no",
			"fieldtype": "Link",
			"options": "Batch",
			"width": 100
		},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 180
		},
		{
			"label": _("Opening Qty"),
			"fieldname": "opening_qty",
			"fieldtype": "Float",
			"width": 80
		},
		{
			"label": _("In Qty"),
			"fieldname": "in_qty",
			"fieldtype": "Float",
			"width": 80
		},
		{
			"label": _("Out Qty"),
			"fieldname": "out_qty",
			"fieldtype": "Float",
			"width": 80
		},
	]
	if filters.get('warehouse'):
		columns +=[
			{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "width": 120,"options": "Warehouse"},
		]

	return columns


def get_conditions(filters):
	conditions = ""
	if not filters.get("from_date"):
		frappe.throw(_("'From Date' is required"))

	if filters.get("to_date"):
		conditions += " and sle.posting_date <= '%s'" % filters["to_date"]
	else:
		frappe.throw(_("'To Date' is required"))
	
	if filters.get("item_group"):
		group_placeholder = ', '.join(f"'{i}'" for i in filters["item_group"])
		conditions += " and i.item_group in (%s)" % group_placeholder
	
	if filters.get("item_code"):
		item_placeholder= ', '.join(f"'{i}'" for i in filters["item_code"])
		conditions += " and sle.item_code in (%s)" % item_placeholder

	if filters.get("not_in_item_code"):
		not_in_item_placeholder= ', '.join(f"'{i}'" for i in filters["not_in_item_code"])
		conditions += " and sle.item_code not in (%s)" % not_in_item_placeholder
	
	if filters.get("company"):
		conditions += " and sle.company = '%s'" % filters["company"]
	
	if filters.get("sales_order"):
		so_doc = frappe.get_doc("Sales Order", filters.sales_order)
		so_item_list = [row.item_code for row in so_doc.items]

		so_item_list_placeholder = ', '.join(f"'{i}'" for i in so_item_list)
		conditions += " and sle.item_code in (%s)" % so_item_list_placeholder

	return conditions


# get all details
def get_stock_ledger_entries(filters):
	conditions = get_conditions(filters)
	if filters.get('warehouse'):
		# return frappe.db.sql("""
		# select item_code, batch_no, warehouse, posting_date, sum(actual_qty) as actual_qty
		# from `tabStock Ledger Entry`
		# where docstatus < 2 and ifnull(batch_no, '') != '' %s
		# group by voucher_no, batch_no, item_code, warehouse
		# order by item_code, warehouse""" %
		# conditions, as_dict=1)
		return frappe.db.sql("""
			select sle.item_code, sle.warehouse, i.item_group, i.image as image, sle.batch_no, sle.posting_date, sum(actual_qty) as actual_qty
			from `tabStock Ledger Entry` as sle 
			JOIN `tabItem` as i on i.item_code = sle.item_code
			JOIN `tabBatch` as batch on batch.name = sle.batch_no
			where sle.is_cancelled = 0 and sle.docstatus < 2 and ifnull(sle.batch_no, '') != '' %s
			group by sle.batch_no, sle.item_code, sle.warehouse
			having sum(actual_qty) != 0
			order by sle.item_code, sle.warehouse""" %
			conditions, as_dict=1)
	else:
		return frappe.db.sql("""
			select sle.item_code, i.item_group, i.image as image, sle.batch_no, sle.posting_date, sum(actual_qty) as actual_qty
			from `tabStock Ledger Entry` as sle 
			JOIN `tabItem` as i on i.item_code = sle.item_code
			JOIN `tabBatch` as batch on batch.name = sle.batch_no
			where sle.is_cancelled = 0 and sle.docstatus < 2 and ifnull(sle.batch_no, '') != '' %s
			group by batch_no, item_code
			having sum(actual_qty) != 0
			order by i.item_group, sle.item_code""" %
			conditions, as_dict=1)


def get_item_warehouse_batch_map(filters, float_precision):
	sle = get_stock_ledger_entries(filters)
	iwb_map = {}

	from_date = getdate(filters["from_date"])
	to_date = getdate(filters["to_date"])
	for d in sle:
		if filters.get('warehouse'):
			iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, {})\
			.setdefault(d.batch_no, frappe._dict({
				"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0
			}))
			qty_dict = iwb_map[d.item_code][d.warehouse][d.batch_no]
		else:
			iwb_map.setdefault(d.item_code, {})\
				.setdefault(d.batch_no, frappe._dict({
					"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0
				}))
			qty_dict = iwb_map[d.item_code][d.batch_no]

		if d.posting_date < from_date:
			qty_dict.opening_qty = flt(qty_dict.opening_qty, float_precision) \
				+ flt(d.actual_qty, float_precision)
		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if flt(d.actual_qty) > 0:
				qty_dict.in_qty = flt(qty_dict.in_qty, float_precision) + flt(d.actual_qty, float_precision)
			else:
				qty_dict.out_qty = flt(qty_dict.out_qty, float_precision) \
					+ abs(flt(d.actual_qty, float_precision))

		qty_dict.bal_qty = flt(qty_dict.bal_qty, float_precision) + flt(d.actual_qty, float_precision)
		qty_dict.item_group = d.item_group
		qty_dict.image = d.image
	return iwb_map


def get_picked_qty(filters,float_precision):
	picked = get_picked_items(filters)
	picked_map = {}
	for d in picked:
		picked_map.setdefault(d.item_code, {})\
			.setdefault(d.batch_no, frappe._dict({
				"pickedqty": 0.0,"unlocked_qty": 0.0
			}))
		picked_dict = picked_map[d.item_code][d.batch_no]
		picked_dict.pickedqty = flt(picked_dict.pickedqty, float_precision) + flt(d.pickedqty, float_precision)
		picked_dict.unlocked_qty += d.unlocked_qty
	return picked_map

def get_picked_items(filters):
	conditions = get_picked_conditions(filters)
	return frappe.db.sql(f"""
				SELECT pli.item_code, pli.batch_no, (pli.qty - (pli.wastage_qty + pli.delivered_qty)) as pickedqty,
				IF(so.lock_picked_qty=0,(pli.qty - (pli.wastage_qty + pli.delivered_qty)),0) as unlocked_qty
				FROM `tabPick List Item` as pli 
				JOIN `tabPick List` as pl on pli.parent = pl.name 
				JOIN `tabItem` as i on i.item_code = pli.item_code
				JOIN `tabSales Order`as so on so.name = pli.sales_order
				WHERE pl.docstatus = 1 {conditions}
				""", as_dict=1)
	
def get_picked_conditions(filters):
	conditions = ""

	if filters.get("to_date"):
		conditions += " and pl.posting_date <= '%s'" % filters["to_date"]
	else:
		frappe.throw(_("'To Date' is required"))
	
	if filters.get("item_group"):
		group_placeholder= ', '.join(f"'{i}'" for i in filters["item_group"])
		conditions += " and pli.item_group in (%s)" % group_placeholder
	
	if filters.get("item_code"):
		item_placeholder= ', '.join(f"'{i}'" for i in filters["item_code"])
		conditions += " and pli.item_code in (%s)" % item_placeholder
	
	if filters.get("not_in_item_code"):
		not_in_item_placeholder= ', '.join(f"'{i}'" for i in filters["not_in_item_code"])
		conditions += " and pli.item_code not in (%s)" % not_in_item_placeholder
	
	
	if filters.get("company"):
		conditions += " and pl.company = '%s'" % filters["company"]
	
	if filters.get("sales_order"):
		so_doc = frappe.get_doc("Sales Order", filters.sales_order)
		so_item_list = [row.item_code for row in so_doc.items]

		so_item_list_placeholder = ', '.join(f"'{i}'" for i in so_item_list)
		
		conditions += " and i.item_code in (%s)" % so_item_list_placeholder

	return conditions


@frappe.whitelist()
def get_picked_item(item_code, batch_no, company, from_date, to_date, bal_qty, total_picked_qty, total_remaining_qty):
	float_precision = 2
	from_date = datetime.datetime.strptime(from_date, '%Y-%m-%d').date()
	to_date = datetime.datetime.strptime(to_date, '%Y-%m-%d').date()

	picked_item = frappe.db.sql(f"""
		SELECT 
			so.delivery_date as date, pli.sales_order, pli.sales_order_item,
			pl.name as pick_list, pli.name as pick_list_item, pli.item_code,
			pli.item_name, (pli.qty - pli.delivered_qty - pli.wastage_qty) as picked_qty,
			pli.delivered_qty, (pli.qty - (pli.wastage_qty + pli.delivered_qty)) as remaining_qty,
			so.customer as customer, so.order_rank, so.per_picked, IF(so.lock_picked_qty=1,'Yes','No') as lock_picked_qty,
			IF(so.lock_picked_qty=0,pli.qty,0) as unlocked_qty
		FROM 
			`tabPick List Item` as pli JOIN `tabPick List` as pl on pli.parent = pl.name
			JOIN `tabSales Order` as so on pli.sales_order = so.name
		WHERE
			pl.docstatus = 1 AND pli.item_code = '{item_code}' AND 
			pli.batch_no = '{batch_no}' AND pl.company = '{company}' 
			AND pl.posting_date <= '{to_date}'
		HAVING
			remaining_qty > 0
		ORDER BY
			so.order_rank
	""", as_dict = 1)
	total_unlocked_qty = 0.0
	for item in picked_item:
		url = get_url_to_form("Sales Order", item.sales_order)
		sales_order_link = "<a href='{url}'>{name}</a>".format(url=url, name=item.sales_order)
		pickurl = get_url_to_form("Pick List", item.pick_list)
		pick_list_link = "<a href='{pickurl}'>{name}</a>".format(pickurl=pickurl, name=item.pick_list)		
		total_unlocked_qty += flt(item.unlocked_qty)
		item.sales_order_link = sales_order_link
		item.pick_list_link = pick_list_link
		item.bal_qty = bal_qty
		item.total_picked_qty = total_picked_qty
		item.total_remaining_qty = total_remaining_qty
		item.batch_no = batch_no
		item.unlocked_qty = total_unlocked_qty
	
	if not picked_item:
		picked_item = [{
			'bal_qty': bal_qty,
			'total_picked_qty': total_picked_qty,
			'total_remaining_qty': total_remaining_qty,
			'unlocked_qty': 0,
			'batch_no': batch_no,
			'item_name': frappe.db.get_value("Item", item_code, 'item_name')
		}]
	
	
	return picked_item