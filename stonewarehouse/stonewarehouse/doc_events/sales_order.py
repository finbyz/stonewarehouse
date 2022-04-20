from __future__ import unicode_literals

import frappe
from frappe import _
from datetime import date,timedelta,datetime
from frappe.utils import flt, cint
from frappe.model.utils import get_fetch_values
from frappe.model.mapper import get_mapped_doc
from frappe.contacts.doctype.address.address import get_company_address
from erpnext.accounts.party import get_party_details
import math
import datetime
from frappe.utils.background_jobs import enqueue, get_jobs

def before_validate(self, method):
	ignore_permission(self)
	
def validate(self, method):
	calculate_order_priority(self)

def on_submit(self, method):
	update_sales_order_total_values(self)
	update_order_rank(self)

def before_validate_after_submit(self, method):
	calculate_order_priority(self)
	update_idx(self)

def before_update_after_submit(self, method):
	calculate_order_priority(self)
	self.calculate_taxes_and_totals()
	update_idx(self)
	update_order_rank(self)
	update_comment(self)

def on_update_after_submit(self, method):
	delete_pick_list(self)
	update_sales_order_total_values(self)
	update_order_rank(self)

def on_cancel(self, method):
	remove_pick_list(self)
	update_sales_order_total_values(self)

# schedule function
def schedule_daily():
	enqueue(execute_schedule_daily, queue= "long", timeout= 10800)

def execute_schedule_daily():
	calculate_order_item_priority()
	calculate_order_rank()


def update_order_rank(self):
	order_rank = frappe.db.sql(f"""
		select
			order_rank, ABS(order_item_priority - {self.order_item_priority}) as difference
		from 
			`tabSales Order`
		WHERE
			status not in ('Completed', 'Draft', 'Cancelled') AND order_rank > 0 HAVING difference > 0 
		order by difference LIMIT 1
	""")[0][0] or 0
	self.db_set('order_rank', order_rank)

def calculate_order_priority(self):
	""" This function is use to calculate priority of order with logic """

	for item in self.items:
		try:
			days = ((datetime.date.today() - datetime.datetime.strptime(self.transaction_date, '%Y-%m-%d').date()) // datetime.timedelta(days = 1)) + 1
		except:
			days = ((datetime.date.today() - self.transaction_date) // datetime.timedelta(days = 1)) + 1
		days = 1 if days <= 0 else days
		base_factor = 4
		item.order_item_priority = cint((days * (base_factor ** (cint(self.order_priority) - 1))) + cint(self.order_priority))
	if self.items[0]:
		self.order_item_priority = self.items[0].order_item_priority

	
def update_comment(self):
	field_list = ['lock_picked_qty','delivery_date']
	for field in field_list:
		if str(self.get(field)) != str(frappe.db.get_value("Sales Order",self.name,field)):
			comment_doc = frappe.new_doc("Comment")
			comment_doc.comment_type = "Info"
			comment_doc.comment_email = frappe.session.user
			comment_doc.reference_doctype = "Sales Order"
			comment_doc.reference_name = self.name

			comment_doc.content = f" changed {field} from {frappe.db.get_value('Sales Order',self.name,field)} to {self.get(field)}"

			comment_doc.save()

#from stonewarehouse.stonewarehouse.doc_events.pick_list import unpick_qty_comment
def delete_pick_list(self):
	pick_list_list = frappe.get_list("Pick List Item", {'sales_order': self.name,'docstatus':1})
	for item in pick_list_list:
		pl = frappe.get_doc("Pick List Item", item.name)
		if not frappe.db.exists("Sales Order Item", pl.sales_order_item):
			if frappe.db.get_value("Sales Order",self.name,'lock_picked_qty'):
				if 'Sales Manager' not in frappe.get_roles():
					frappe.throw("Only Sales Manager is allowed to unpick")

			if pl.docstatus == 1:
				pl.cancel()
				unpick_qty_comment(pl.parent,self.name, f"Unpicked full Qty from item {pl.item_code}")
			pl.delete()

def unpick_qty_comment(reference_name, sales_order, data):
	comment_pl_doc = frappe.new_doc("Comment")
	comment_pl_doc.comment_type = "Info"
	comment_pl_doc.comment_email = frappe.session.user
	comment_pl_doc.reference_doctype = "Pick List"
	comment_pl_doc.reference_name = reference_name

	comment_pl_doc.content = data

	comment_pl_doc.save()

	comment_so_doc = frappe.new_doc("Comment")
	comment_so_doc.comment_type = "Info"
	comment_so_doc.comment_email = frappe.session.user
	comment_so_doc.reference_doctype = "Sales Order"
	comment_so_doc.reference_name = sales_order

	comment_so_doc.content = data

	comment_so_doc.save()

def ignore_permission(self):
	""" This function is use to ignore save permission while saving sales order """

	self.flags.ignore_permissions = True
	if not self.order_priority:
		self.order_priority = frappe.db.get_value("Customer", self.customer, 'customer_priority')
	if self._action == "update_after_submit":
		self.flags.ignore_validate_update_after_submit = True


def remove_pick_list(self):
	from stonewarehouse.stonewarehouse.doc_events.pick_list import update_delivered_percent
	parent_doc = []

	for item in self.items:
		if item.picked_qty:
			for picked_item in frappe.get_all("Pick List Item", {'sales_order': self.name, 'sales_order_item': item.name}):
				doc = frappe.get_doc("Pick List Item", picked_item.name)

				if doc.delivered_qty:
					frappe.throw(_("You can not cancel this Sales Order, Delivery Note already there for this Sales Order."))

				doc.cancel()
				doc.delete()

				for dn in frappe.get_all("Delivery Note Item", {'against_pick_list': doc.name}):
					dn_doc = frappe.get_doc("Delivery Note Item", dn.name)
					frappe.throw(dn_doc.name)

					dn_doc.db_set('against_pick_list', None)
					dn_doc.db_set('pl_detail', None)

				parent_doc.append(doc.parent)
				item.db_set('picked_qty', 0)

	for pl in frappe.get_all("Pick List", {'sales_order': self.name}):
		frappe.db.set_value("Pick List", pl.name, 'sales_order', None)

	for item in set(parent_doc):
		update_delivered_percent(frappe.get_doc("Pick List", item))

def update_idx(self):
	for idx, item in enumerate(self.items):
		item.idx = idx + 1

def update_sales_order_total_values(self):
	""" This function is use to change total value on submit and cancel of sales order, pick list and delivery note """
	
	if self.status == "Close":
		frappe.throw("Can not create pick list against close sales order.")
		
	qty = 0
	total_picked_qty = 0.0
	total_picked_weight = 0.0
	total_delivered_qty = 0.0
	total_wastage_qty = 0.0
	total_deliverd_weight = 0.0
	total_qty = 0.0
	total_net_weight = 0.0


	for row in self.items:
		qty += row.qty
		row.db_set('picked_weight',flt(row.weight_per_unit * row.picked_qty))
		total_picked_qty += row.picked_qty
		total_picked_weight += row.picked_weight
		total_delivered_qty += row.delivered_qty
		total_wastage_qty += row.wastage_qty
		total_deliverd_weight += flt(row.weight_per_unit * row.delivered_qty)
		total_qty += row.qty
		row.db_set('total_weight',flt(row.weight_per_unit * row.qty))
		total_net_weight += row.total_weight

	if qty:
		per_picked = (total_picked_qty / qty) * 100
	else:
		per_picked = 0

	self.db_set('total_qty', total_qty)
	self.db_set('total_net_weight', total_net_weight)
	self.db_set('per_picked', per_picked)
	self.db_set('total_picked_qty', flt(total_picked_qty))
	self.db_set('total_picked_weight', total_picked_weight)
	self.db_set('total_delivered_qty', total_delivered_qty)
	self.db_set('picked_to_be_delivered_qty', self.total_picked_qty - flt(total_delivered_qty - flt(total_wastage_qty)))
	self.db_set('picked_to_be_delivered_weight', flt(total_picked_weight) - total_deliverd_weight)

@frappe.whitelist()
def change_customer(customer, doc):
	""" This function is use to change customer on submited document """

	so = frappe.get_doc("Sales Order",doc)
	customer_data = get_party_details(customer, "Customer")

	so.db_set('customer', customer)
	so.db_set('primary_customer',frappe.db.get_value("Customer",customer,'primary_customer') or customer)
	so.db_set('title', customer)
	so.db_set('customer_name', frappe.db.get_value("Customer",customer,'customer_name'))
	so.db_set('order_priority', frappe.db.get_value("Customer",customer,'customer_priority'))	
	so.db_set('customer_address', customer_data['customer_address'])
	so.db_set('address_display', customer_data['address_display'])
	so.db_set('shipping_address_name', customer_data['shipping_address_name'])
	so.db_set('shipping_address', customer_data['shipping_address'])
	so.db_set('contact_person', customer_data['contact_person'])
	so.db_set('contact_display', customer_data['contact_display'])
	so.db_set('contact_email', customer_data['contact_email'])
	so.db_set('contact_mobile', customer_data['contact_mobile'])
	so.db_set('contact_phone', customer_data['contact_phone'])
	so.db_set('customer_group', customer_data['customer_group'])

	return "Customer Changed Successfully."

@frappe.whitelist()
def get_tax_template(tax_category, company, tax_paid=0):
	if not tax_category:
		frappe.throw("Please Select Tax Category")
	if frappe.db.exists("Sales Taxes and Charges Template",{'tax_paid':tax_paid,'tax_category':tax_category,'company':company}):
		return frappe.db.get_value("Sales Taxes and Charges Template",{'tax_paid':tax_paid,'tax_category':tax_category,'company':company},'name')

@frappe.whitelist()
def make_pick_list(source_name, target_doc=None):
	def update_item_quantity(source, target, source_parent):
		target.qty = flt(source.qty) - flt(source.picked_qty) - flt(source.delivered_without_pick)
		target.so_qty = flt(source.qty)
		target.stock_qty = (flt(source.qty) - flt(source.picked_qty)) * flt(source.conversion_factor)
		target.picked_qty = source.picked_qty
		target.remaining_qty = target.so_qty - target.qty - target.picked_qty
		target.customer = source_parent.customer
		target.date = source_parent.transaction_date
		target.delivery_date = source.delivery_date
		target.so_picked_percent = source_parent.per_picked
		target.warehouse = None
		target.order_item_priority = source.order_item_priority
		target.so_delivered_without_pick = source.delivered_without_pick

	doc = get_mapped_doc('Sales Order', source_name, {
		'Sales Order': {
			'doctype': 'Pick List',
			'validation': {
				'docstatus': ['=', 1]
			}
		},
		'Sales Order Item': {
			'doctype': 'Pick List Item',
			'field_map': {
				'parent': 'sales_order',
				'name': 'sales_order_item'
			},
			'field_no_map': [
				'warehouse'
			],
			'postprocess': update_item_quantity,
			'condition': lambda doc: abs(doc.picked_qty) < abs(doc.qty) and doc.delivered_by_supplier!=1
		},
	}, target_doc)

	doc.purpose = 'Delivery'
	doc.set_item_locations()
	return doc

@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, skip_item_mapping=False):
	""" This function is use to make delivery note from create button replacing the original erpnext function """

	def set_missing_values(source, target):
		target.ignore_pricing_rule = 1
		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		target.run_method("calculate_taxes_and_totals")

		if source.company_address:
			target.update({'company_address': source.company_address})
		else:
			# set company address
			target.update(get_company_address(target.company))

		if target.company_address:
			target.update(get_fetch_values("Delivery Note", 'company_address', target.company_address))

	def update_item(source, target, source_parent):
		for i in source.items:
			if frappe.db.get_value("Item", i.item_code, 'is_stock_item'):
				for j in frappe.get_all("Pick List Item", filters={"sales_order": source.name, "sales_order_item": i.name, "docstatus": 1}):
					pick_doc = frappe.get_doc("Pick List Item", j.name)
					
					warehouse_query = frappe.db.sql(f"""
					SELECT
						sle.warehouse
					FROM 
						`tabStock Ledger Entry` sle
					INNER JOIN
						`tabBatch` batch on sle.batch_no = batch.name
					WHERE
						sle.is_cancelled = 0 and sle.item_code = '{pick_doc.item_code}' AND
						batch.docstatus < 2 AND
						sle.batch_no = '{pick_doc.batch_no}'
					GROUP BY 
						warehouse having sum(sle.actual_qty) > 0
					ORDER BY 
						sum(sle.actual_qty) desc
					limit 1""")

					warehouse = None
					if warehouse_query:
						warehouse = warehouse_query[0][0]
					
					if pick_doc.qty - pick_doc.delivered_qty:
						target.append('items',{
							'item_code': pick_doc.item_code,
							'qty': pick_doc.qty - pick_doc.delivered_qty,
							'rate': i.rate,
							'against_sales_order': source.name,
							'so_detail': i.name,
							'against_pick_list': pick_doc.parent,
							'pl_detail': pick_doc.name,
							'warehouse': warehouse,
							'batch_no': pick_doc.batch_no,
							'picked_qty': pick_doc.qty - pick_doc.delivered_qty
						})

			else:
				target.append('items',{
					'item_code': i.item_code,
					'qty': i.qty - i.delivered_qty,
					'rate': i.rate,
					'against_sales_order': source.name,
					'so_detail': i.name,
					'warehouse': i.warehouse,
					'batch_no': ''
				})
			
		target_items = []
		target_item_dict = {}

		if not target.get('items'):
			target.items = []

		for i in target.items:
			if not target_item_dict.get(i.so_detail):
				target_item_dict[i.so_detail] = 0
			
			target_item_dict[i.so_detail] += i.qty

		for i in source.items:
			if target_item_dict.get(i.name):
				if i.qty > target_item_dict.get(i.name):
					target.append('items',{
					'item_code': i.item_code,
					'qty': i.qty - i.delivered_qty - target_item_dict[i.name],
					'rate': i.rate,
					'against_sales_order': source.name,
					'so_detail': i.name,
					'warehouse': i.warehouse,
					'batch_no': ''
				})
			else:
				target.append('items',{
					'item_code': i.item_code,
					'qty': i.qty - i.delivered_qty,
					'rate': i.rate,
					'against_sales_order': source.name,
					'so_detail': i.name,
					'warehouse': i.warehouse,
					'batch_no': ''
				})
	mapper = {
		"Sales Order": {
			"doctype": "Delivery Note",
			"validation": {
				"docstatus": ["=", 1]
			},
			"postprocess": update_item
		},
		"Sales Taxes and Charges": {
			"doctype": "Sales Taxes and Charges",
			"add_if_empty": True
		},
		"Sales Team": {
			"doctype": "Sales Team",
			"add_if_empty": True
		}
	}

	target_doc = get_mapped_doc("Sales Order", source_name, mapper, target_doc, set_missing_values)
	return target_doc

def calculate_order_item_priority():
	data = frappe.db.sql(f"""
		SELECT
			soi.`name`, so.`transaction_date`, so.`order_priority`
		FROM
			`tabSales Order Item` as soi JOIN `tabSales Order` as so ON so.`name` = soi.`parent`
		WHERE
			soi.`qty` > soi.`delivered_qty` AND
			so.`docstatus` = 1
			AND so.status not in ('Completed', 'Stopped', 'Hold', 'Closed')
	""", as_dict = 1)

	for soi in data:
		days = ((datetime.date.today() - soi.transaction_date) // datetime.timedelta(1)) + 1
		base_factor = 4
		order_item_priority = cint((days * (base_factor ** (cint(soi.order_priority) - 1))) + cint(soi.order_priority))

		frappe.db.set_value("Sales Order Item", soi.name, 'order_item_priority', order_item_priority, update_modified = True)

def calculate_order_rank():
	companies_list = frappe.get_list("Company")

	data = frappe.db.sql(f"""
		SELECT
			so.name as so_name From `tabSales Order` as so
		WHERE
			so.`per_delivered` < 100 AND
			so.`docstatus` = 1
			AND so.status not in ('Completed', 'Stopped', 'Hold', 'Closed')
	""", as_dict = 1)

	for soi in data:
		doc = frappe.get_doc("Sales Order", soi.so_name)
		doc.db_set('order_item_priority', doc.items[0].order_item_priority, update_modified = False)
	
	for i in companies_list:
		priority = frappe.db.sql(f"""
			select 
				name, row_number() over(order by order_item_priority desc, transaction_date desc) as rank
			from
				`tabSales Order` 
			WHERE
				docstatus = 1 and 
				status not in ('Closed', 'Stoped', 'Completed', 'Hold') and 
				per_delivered < 100 
				AND company = '{i.name}'
			order by 
				order_item_priority desc
		""", as_dict = True)

		for item in priority:
			print(item.name, item.rank)
			frappe.db.set_value("Sales Order", item.name, 'order_rank', item.rank, update_modified = False)


@frappe.whitelist()
def update_order_rank_(date, order_priority, company):
	try:
		days = ((datetime.date.today() - datetime.datetime.strptime(date, '%Y-%m-%d').date()) // datetime.timedelta(days = 1)) + 1
	except:
		days = ((datetime.date.today() - date) // datetime.timedelta(days = 1)) + 1
	days = 1 if days <= 0 else days
	base_factor = 4
	order_item_priority = cint((days * (base_factor ** (cint(order_priority) - 1))) + cint(order_priority))

	order_rank_tuple = frappe.db.sql(f"""
	select 
		order_rank, ABS(order_item_priority - {order_item_priority}) as difference
	from
		`tabSales Order` 
	WHERE
		status not in ('Completed', 'Draft', 'Cancelled', 'Hold') 
		AND order_rank > 0
		AND company = '{company}'
	HAVING
		difference > 0 
	ORDER BY
		difference LIMIT 1
	""")
	if order_rank_tuple:
		if order_rank_tuple[0]:
			order_rank = order_rank_tuple[0][0] or 0
		else:
			order_rank = 0
	else:
		order_rank = 0

	return {'order_item_priority': order_item_priority, 'order_rank': order_rank}


		
