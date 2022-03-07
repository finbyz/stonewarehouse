# Copyright (c) 2013, Finbyz Tech. Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	columns, data = [], []
	columns = get_columns_details()
	data = get_data(filters)

	dispatch_dict = {}
	non_dispatch_list = []
	new_data = []
	if filters.get("ready_to_dispatch"):
		for row in data:
			if flt(row.dispatch_percentage) < 100 and flt(row.actual_qty) >= flt(row.qty_to_deliver) and row.name not in non_dispatch_list:
				if row.name not in dispatch_dict:
					dispatch_dict[row.name] = [row]
				else:
					dispatch_dict[row.name].append(row)

			else:
				non_dispatch_list.append(row.name)
				if row.name in dispatch_dict:
					del dispatch_dict[row.name]

		for so, row in dispatch_dict.items():
			new_data.extend(row)

		data = new_data

	return columns, data

def get_purchase_receipt_data():
	pr_map = {}
	# data = frappe.db.sql("select purchase_order_item as po_detail,qty from `tabPurchase Receipt Item` where docstatus = 1",as_dict=1)
	data = frappe.db.sql("""
		select
			pri.purchase_order_item as po_detail,pri.qty, pr.posting_date
		from
			`tabPurchase Receipt Item` as pri
			JOIN `tabPurchase Receipt` as pr on pr.name = pri.parent
		where pri.docstatus = 1
	""",as_dict=1)

	for pr in data:
		if pr.po_detail:
			pr_map.setdefault(pr.po_detail,[pr.qty, pr.posting_date])
	return pr_map

def get_purchase_invoice_data():

	pi_map = {}
	data = frappe.db.sql("""select pii.po_detail,pii.qty from `tabPurchase Invoice Item` as pii
			JOIN `tabPurchase Invoice` as pi on pi.name = pii.parent
			where pi.docstatus = 1 and pi.update_stock = 1""",as_dict=1)
	for pi in data:
		if pi.po_detail:
			pi_map.setdefault(pi.po_detail,pi.qty)
	return pi_map

def get_purchase_order_data():

	po_map = {}
	data = frappe.db.sql("""select po.material_request_item,po.parent as purchase_order,po.qty as po_qty,po.name as po_detail, pop.schedule_date, pop.supplier from `tabPurchase Order Item` as po
	JOIN `tabPurchase Order` as pop on pop.name = po.parent 
	where po.docstatus = 1""",as_dict=1)
	for po in data:
		if po.material_request_item:
			po_map.setdefault(po.material_request_item,po)
	return po_map

def get_sales_invoice_data():
	si_map = {}
	data = frappe.db.sql("""
		select
			sii.so_detail, si.name, si.posting_date
		from
			`tabSales Invoice Item` as sii
			JOIN `tabSales Invoice` as si on si.name = sii.parent
		where si.docstatus = 1
	""",as_dict=1)

	for si in data:
		if si.so_detail:
			si_map.setdefault(si.so_detail,[si.name, si.posting_date])
	return si_map

def get_filters_conditions(filters):
	conditions = ''
	if filters.get('name'):
		conditions += " and so.name = '{}'".format(filters.get('name'))

	if filters.get('customer'):
		conditions += " and so.customer = '{}'".format(filters.get('customer'))

	if filters.get('company'):
		conditions += " and so.company = '{}'".format(filters.get('company'))

	if filters.get('item_code'):
		conditions += " and soi.item_code = '{}'".format(filters.get('item_code'))

	if filters.get('from_date') and filters.get('to_date'):
		conditions += " and so.transaction_date BETWEEN '{}' and '{}'".format(filters.get('from_date'),filters.get('to_date'))
	return conditions

def get_data(filters):
	conditions = get_filters_conditions(filters)
	data = frappe.db.sql("""
		select 
			so.name,so.status,so.customer,so.transaction_date, so.per_delivered as dispatch_percentage, soi.item_code,soi.qty,
			soi.delivered_qty, (soi.qty - soi.delivered_qty) as qty_to_deliver,soi.delivery_date,
			soi.item_name,soi.item_group,soi.warehouse, soi.name as so_item_name,
			b.actual_qty,b.projected_qty,
			CASE
				WHEN mr.docstatus=1 THEN mr.parent
			END AS material_request,
			CASE
				WHEN mr.docstatus=1 THEN mr.qty
			END AS mr_qty,
			CASE
				WHEN mr.docstatus=1 THEN mr.name
			END AS mr_name
		from 
			`tabSales Order` as so
			JOIN `tabSales Order Item` as soi on soi.parent=so.name
			LEFT JOIN `tabBin` as b on b.item_code = soi.item_code and b.warehouse=soi.warehouse
			LEFT JOIN `tabMaterial Request Item` as mr on mr.sales_order_item = soi.name
		where
			so.docstatus=1 and so.status not in ("Cancelled", "Closed","Completed"){}
		order by
			so.transaction_date asc
	""".format(conditions),as_dict=1)

	po_map = get_purchase_order_data()
	pr_map = get_purchase_receipt_data()
	pi_map = get_purchase_invoice_data()
	si_map = get_sales_invoice_data()

	for row in data:
		if row.mr_name:
			po = po_map.get(row.mr_name)
			if po:
				row.purchase_order = po.purchase_order
				row.po_qty = po.po_qty
				row.po_detail = po.po_detail
				row.schedule_date = po.schedule_date
				row.supplier = po.supplier
		if row.po_detail:
			qty_date = pr_map.get(row.po_detail)
			if qty_date and qty_date[0]:
				row.received_qty = qty_date[0]
				row.purchase_receipt_date = qty_date[1] 
			else:
				qty = pi_map.get(row.po_detail)
				if qty:
					row.received_qty = qty
		
		if row.so_item_name:
			si_date = si_map.get(row.so_item_name)
			if si_date:
				row.si_name = si_date[0]
				row.si_date = si_date[1]
	return data

def get_columns_details():
	columns = [

		{ "label": _("Sales Order"),"fieldname": "name","fieldtype": "Link","options":"Sales Order","width": 130},
		{ "label": _("Status"),"fieldname": "status","fieldtype": "Data","width": 102},
		{ "label": _("Customer"),"fieldname": "customer","fieldtype": "Link","options":"Customer","width": 130},
		{ "label": _("Date"),"fieldname": "transaction_date","fieldtype": "Date","width": 80},
		{ "label": _("Sales Invoice"),"fieldname": "si_name","fieldtype": "Link","options":"Sales Invoice","width": 130},
		{ "label": _("Sales Invoice Date"),"fieldname": "si_date","fieldtype": "Date","width": 80},
		{ "label": _("Item Code"),"fieldname": "item_code","fieldtype": "Link","options":"Item","width": 100},
		{ "label": _("Qty"),"fieldname": "qty","fieldtype": "Float","width": 70},
		{ "label": _("Delivered Qty"),"fieldname": "delivered_qty","fieldtype": "Float","width": 70},
		{ "label": _("To Deliver Qty"),"fieldname": "qty_to_deliver","fieldtype": "Float","width": 70},
		{ "label": _("Available Qty"),"fieldname": "actual_qty","fieldtype": "Float","width": 70},
		{ "label": _("Projected Qty"),"fieldname": "projected_qty","fieldtype": "Float","width": 70},
		{ "label": _("Delivery Date"),"fieldname": "delivery_date","fieldtype": "Date","width": 80},
		{ "label": _("Material Request"),"fieldname": "material_request","fieldtype": "Link","options":"Material Request","width": 130},
		{ "label": _("MR Qty"),"fieldname": "mr_qty","fieldtype": "Float","width": 70},
		{ "label": _("Purchase Order"),"fieldname": "purchase_order","fieldtype": "Link","options":"Purchase Order","width": 120},
		{ "label": _("PO Qty"),"fieldname": "po_qty","fieldtype": "Float","width": 70},
		{ "label": _("Received Qty"),"fieldname": "received_qty","fieldtype": "Float","width": 70},
		{ "label": _("Purchase Receipt Date"),"fieldname": "purchase_receipt_date","fieldtype": "Date","width": 80},
		{ "label": _("PO Expected Date"),"fieldname": "schedule_date","fieldtype": "Date","width": 80},
		{ "label": _("PO Supplier"),"fieldname": "supplier","fieldtype": "Link","options":"Supplier","width": 100},
		{ "label": _("Item Name"),"fieldname": "item_name","fieldtype": "Data","width": 100},
		{ "label": _("Item Group"),"fieldname": "item_group","fieldtype": "Link","options":"Item Group","width": 100},
		{ "label": _("Warehouse"),"fieldname": "warehouse","fieldtype": "Link","options":"Warehouse","width": 100},

	]
	return columns