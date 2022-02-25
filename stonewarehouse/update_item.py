import frappe
from frappe import _
from frappe.utils import flt, cint, get_url_to_form
import json
from erpnext.controllers.accounts_controller import set_order_defaults, validate_and_delete_children
from stonewarehouse.stonewarehouse.doc_events.pick_list import unpick_item,unpick_qty_comment


@frappe.whitelist()
def update_child_qty_rate(parent_doctype, trans_items, parent_doctype_name, child_docname="items"):
	data = json.loads(trans_items)

	sales_doctypes = ['Sales Order', 'Sales Invoice', 'Delivery Note', 'Quotation']
	parent = frappe.get_doc(parent_doctype, parent_doctype_name)

	validate_and_delete_children(parent, data)

	for d in data:
		new_child_flag = False
		if not d.get('item_code'):
			frappe.throw("Please Enter Item Code Properly.")
			
		if not d.get("docname"):
			new_child_flag = True
			child_doctype = "Sales Order Item" if parent_doctype == "Sales Order" else "Purchase Order Item" 
			child_item = set_order_defaults(parent_doctype, parent_doctype_name, child_doctype, child_docname, d)
			# if parent_doctype == "Sales Order":
			# 	child_item  = set_sales_order_defaults(parent_doctype, parent_doctype_name, child_docname, d)
			# if parent_doctype == "Purchase Order":
			# 	child_item = set_purchase_order_defaults(parent_doctype, parent_doctype_name, child_docname, d)
		else:
			child_item = frappe.get_doc(parent_doctype + ' Item', d.get("docname"))
			
			if child_item.item_code != d.get("item_code"):
				frappe.throw("Please delete old item row and add new row for item change")

			if child_item.item_code == d.get("item_code") and (not d.get("rate") or flt(child_item.get("rate")) == flt(d.get("rate"))) and flt(child_item.get("qty")) == flt(d.get("qty")):
				continue

		comment = ''
		
		if d.get('item_code') != child_item.item_code:
			comment += f""" Item Change From <a href='{get_url_to_form("Item", child_item.item_code)}'>{frappe.bold(child_item.item_code)}</a> to <a href='{frappe.bold(get_url_to_form("Item", d.get("item_code")))}'>{d.get('item_code')}.</a>"""
		if d.get('qty') != child_item.qty:
			comment += f" Qty Change From {child_item.qty} to {d.get('qty')}."
		if d.get('rate') != child_item.rate:
			comment += f" Rate Changed in Item: {d.get('item_code')}"

		if parent_doctype == "Sales Order" and flt(d.get("qty")) < flt(child_item.delivered_qty):
			frappe.throw(_("Cannot set quantity less than delivered quantity"))

		if parent_doctype == "Purchase Order" and flt(d.get("qty")) < flt(child_item.received_qty):
			frappe.throw(_("Cannot set quantity less than received quantity"))
		
		if parent_doctype == "Sales Order" and d.get("item_code") != child_item.item_code and child_item.delivered_qty:
			frappe.throw(_("Cannot change item as delivery note is already made"))

		if parent_doctype == "Sales Order" and (d.get("rate")):
			if d.get("rate") and flt(d.get("rate")) != child_item.rate and child_item.delivered_qty:
				frappe.throw(_("Cannot change rate as delivery note is already made"))
		
		# if parent_doctype == "Sales Order" and flt(d.get("qty")) != flt(child_item.qty) and child_item.delivered_qty:
		# 	frappe.throw(_("Cannot change qty as delivery note is already made"))
		item_name, item_group, description = frappe.db.get_value("Item", d.get("item_code"), ["item_name","item_group","description"])
		child_item.qty = flt(d.get("qty"))
		child_item.item_name = item_name
		child_item.item_group = item_group
		child_item.description = description or item_name
		child_item.parent_item_group = frappe.db.get_value("Item Group",item_group,"parent_item_group")
		if parent_doctype == "Sales Order":
			packing_type = frappe.db.get_value("Company",parent.company,"default_packing_type")
			if packing_type and not child_item.packing_type:
				child_item.packing_type=packing_type
		precision = child_item.precision("rate") or 2

		
		if parent_doctype == "Sales Order" and d.get("item_code") != child_item.item_code:
			for picked_item in frappe.get_all("Pick List Item", {'sales_order':child_item.parent, 'sales_order_item':child_item.name}):
				pl = frappe.get_doc("Pick List Item", picked_item.name)

				user = frappe.get_doc("User",frappe.session.user)
				role_list = [r.role for r in user.roles]
				if frappe.db.get_value("Sales Order",child_item.parent,'lock_picked_qty'):
					dispatch_person_user = frappe.db.get_value("Sales Person",frappe.db.get_value("Sales Order",child_item.parent,'dispatch_person'),'user')
					if dispatch_person_user:
						if user.name != dispatch_person_user and 'Local Admin' not in role_list and 'Sales Head' not in role_list:
							frappe.throw("Only {} is allowed to unpick".format(dispatch_person_user))
				pl.cancel()
				pl.delete()
			
				unpick_qty_comment(pl.parent, child_item.parent, f"Unpicked full Qty from item {child_item.item_code}")
						
			child_item.picked_qty = 0
			frappe.msgprint(_(f"All Pick List For Item {child_item.item_code} has been deleted."))

		if parent_doctype == "Sales Order" and (flt(d.get("qty")) < flt(child_item.picked_qty) and d.get("item_code") == child_item.item_code):
			diff_qty = flt(child_item.picked_qty) - flt(d.get("qty"))
			unpick_item(child_item.parent, child_item.name, sales_order_differnce_qty = diff_qty)
			
			child_item.picked_qty = child_item.picked_qty - diff_qty
		
		if not flt(d.get('rate')):
			d['rate'] = child_item.rate

		
		if flt(child_item.billed_amt, precision) > flt(flt(d.get("rate")) * flt(d.get("qty")), precision):
			frappe.throw(_("Row #{0}: Cannot set Rate if amount is greater than billed amount for Item {1}.")
						 .format(child_item.idx, child_item.item_code))
		else:
			child_item.rate = flt(d.get("rate"))
		child_item.item_code = d.get('item_code')
		
		
		if flt(child_item.price_list_rate):
			if flt(child_item.rate) > flt(child_item.price_list_rate):
				#  if rate is greater than price_list_rate, set margin
				#  or set discount
				child_item.discount_percentage = 0

				if parent_doctype in sales_doctypes:
					child_item.margin_type = "Amount"
					child_item.margin_rate_or_amount = flt(child_item.rate - child_item.price_list_rate,
						child_item.precision("margin_rate_or_amount"))
					child_item.rate_with_margin = child_item.rate
			else:
				child_item.discount_percentage = flt((1 - flt(child_item.rate) / flt(child_item.price_list_rate)) * 100.0,
					child_item.precision("discount_percentage"))
				child_item.discount_amount = flt(
					child_item.price_list_rate) - flt(child_item.rate)

				if parent_doctype in sales_doctypes:
					child_item.margin_type = ""
					child_item.margin_rate_or_amount = 0
					child_item.rate_with_margin = 0

		child_item.flags.ignore_validate_update_after_submit = True
		if new_child_flag:
			child_item.idx = len(parent.items) + 1
			child_item.insert()
		else:
			child_item.save()

		if comment and not new_child_flag:
			comment_doc = frappe.new_doc("Comment")
			comment_doc.comment_type = "Info"
			comment_doc.comment_email = frappe.session.user
			comment_doc.reference_doctype = "Sales Order"
			comment_doc.reference_name = child_item.parent

			comment_doc.content = f" changed Row: {child_item.idx}" + comment

			comment_doc.save()



	parent.reload()
	parent.flags.ignore_validate_update_after_submit = True
	parent.flags.ignore_permissions = True
	parent.set_qty_as_per_stock_uom()
	parent.calculate_taxes_and_totals()
	if parent_doctype == "Sales Order":
		parent.set_gross_profit()
	frappe.get_doc('Authorization Control').validate_approving_authority(parent.doctype,
		parent.company, parent.base_grand_total)

	parent.set_payment_schedule()
	if parent_doctype == 'Purchase Order':
		parent.validate_minimum_order_qty()
		parent.validate_budget()
		if parent.is_against_so():
			parent.update_status_updater()
	else:
		parent.check_credit_limit()
	parent.save()

	if parent_doctype == 'Purchase Order':
		update_last_purchase_rate(parent, is_submit = 1)
		parent.update_prevdoc_status()
		parent.update_requested_qty()
		parent.update_ordered_qty()
		parent.update_ordered_and_reserved_qty()
		parent.update_receiving_percentage()
		if parent.is_subcontracted == "Yes":
			parent.update_reserved_qty_for_subcontract()
	else:
		parent.update_reserved_qty()
		parent.update_project()
		parent.update_prevdoc_status('submit')
		parent.update_delivery_status()

	parent.update_blanket_order()
	parent.update_billing_percentage()
	parent.set_status()
