import frappe, re
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.contacts.doctype.address.address import get_company_address
from frappe.model.utils import get_fetch_values
from frappe.utils import flt
from stonewarehouse.stonewarehouse.doc_events.sales_order import update_sales_order_total_values
from erpnext.stock.doctype.serial_no.serial_no import get_delivery_note_serial_no



def before_validate(self, method):
	for item in self.items:
		if (not item.rate) and (item.so_detail):
			item.rate = frappe.db.get_value("Sales Order Item", item.so_detail, 'rate')

	validate_item_from_so(self)
	sales_order_list = list(set([x.against_sales_order for x in self.items if x.against_sales_order]))

	for x in sales_order_list:
		so_doc = frappe.get_doc("Sales Order",x)
		so_doc.db_set("customer",self.customer)
		so_doc.db_set("title",self.customer)
		so_doc.db_set("customer_name",self.customer_name)

def validate(self, method):
	if self._action == "submit":
		check_rate_qty(self)
	update_lock_qty(self)
	validate_item_from_picklist(self)
	calculate_totals(self)
		
def before_submit(self, method):
	check_item_without_pick(self)
	update_status_pick_list_and_sales_order(self)

def on_submit(self,method):
	wastage_stock_entry(self)
	for item in self.items:
		if item.against_sales_order:
			update_sales_order_total_values(frappe.get_doc("Sales Order", item.against_sales_order))


def on_cancel(self, method):
	# # below changes because of wastage qty issue
	# new_items=[]
	# for i in self.items:
	# 	new_items.append(frappe._dict(i.__dict__))
	# items = sorted(new_items, key = lambda i: i['wastage_qty'],reverse=True)
	# for item in items:
	# # Changes complete
	for item in self.items:
		if item.against_pick_list:
			pick_list_item = frappe.get_doc("Pick List Item", item.pl_detail)
			delivered_qty = pick_list_item.delivered_qty - item.qty
			wastage_qty = pick_list_item.wastage_qty - item.wastage_qty
			frappe.db.set_value("Pick List Item", pick_list_item.name, 'delivered_qty', flt(delivered_qty))
			frappe.db.set_value("Pick List Item", pick_list_item.name, 'wastage_qty', flt(wastage_qty))
	
		if item.against_sales_order:
			sales_order_item = frappe.get_doc("Sales Order Item", item.so_detail)
			wastage_qty = sales_order_item.wastage_qty - item.wastage_qty
			frappe.db.set_value("Sales Order Item", sales_order_item.name, 'wastage_qty', flt(wastage_qty))
			if item.against_pick_list:
				if sales_order_item.picked_qty + wastage_qty > sales_order_item.qty:
					frappe.throw(f"Please Unpick {sales_order_item.picked_qty + wastage_qty - sales_order_item.qty} for Sales Order {sales_order_item.parent} Row: {sales_order_item.idx}")
				
				frappe.db.set_value("Sales Order Item", sales_order_item.name, 'picked_qty', flt(sales_order_item.picked_qty + item.wastage_qty))
			update_sales_order_total_values(frappe.get_doc("Sales Order", item.against_sales_order))
		
		if not item.against_pick_list and item.against_sales_order:
			so_delivered_without_pick = frappe.db.get_value("Sales Order Item", item.so_detail, 'delivered_without_pick')
			frappe.db.set_value("Sales Order Item", item.so_detail, 'delivered_without_pick', item.qty - so_delivered_without_pick)
	update_status_pick_list(self)
	cancel_wastage_entry(self)

def update_lock_qty(self):
	if self.is_new():	
		if self.items[0].against_sales_order:
			so_doc = frappe.get_doc("Sales Order",self.items[0].against_sales_order)
			so_doc.db_set('lock_picked_qty',1)

def validate_item_from_so(self):
	for row in self.items:
		if frappe.db.exists("Sales Order Item",row.so_detail):
			so_item = frappe.db.get_value("Sales Order Item",row.so_detail,"item_code")
			if row.item_code != so_item:
				frappe.throw(_(f"Row: {row.idx}: Not allowed to change item {frappe.bold(row.item_code)}."))

def validate_item_from_picklist(self):
	for row in self.items:
		if row.pl_detail:
			if frappe.db.exists("Pick List Item",row.pl_detail):
				picked_qty = flt(frappe.db.get_value("Pick List Item",row.pl_detail,"qty"))
				if flt(row.qty) > picked_qty:
					frappe.throw(_(f"Row: {row.idx}: Delivered Qty {frappe.bold(row.qty)} can not be higher than picked Qty {frappe.bold(picked_qty)} for item {frappe.bold(row.item_code)}."))
			else:
				frappe.throw(_(f"Row: {row.idx}: The item {frappe.bold(row.item_code)} has been unpicked from picklist {frappe.bold(row.against_pick_list)}"))

def calculate_totals(self):
	for d in self.items:
		#d.wastage_qty = flt(d.picked_qty - d.qty)
		d.total_weight = flt(d.weight_per_unit * d.qty)
	self.total_qty = sum([row.qty for row in self.items])
	self.total_net_weight = sum([row.total_weight for row in self.items])

def check_item_without_pick(self):
	
	item_without_pick_list_dict = {}
	for row in self.items:
		if not row.pl_detail and row.so_detail:
			if not item_without_pick_list_dict.get(row.so_detail):
				item_without_pick_list_dict[row.so_detail] = 0
			
			item_without_pick_list_dict[row.so_detail] += row.qty

	for key, row in item_without_pick_list_dict.items():
		item_code, parent, so_qty, so_picked_qty, so_delivered_qty, so_delivered_without_pick = frappe.db.get_value("Sales Order Item", key, ['item_code', 'parent', 'qty', 'picked_qty', 'delivered_qty', 'delivered_without_pick'])
		
		allowed_qty = so_qty - so_picked_qty - so_delivered_without_pick
		
		if allowed_qty < row:
			frappe.throw(f"You can not deliver more than {allowed_qty} without Pick List for Item {item_code} for Sales Order {parent}.")

def update_status_pick_list_and_sales_order(self):
	for item in self.items:
		if item.against_pick_list:
			pick_list_item = frappe.get_doc("Pick List Item", item.pl_detail)
			if item.batch_no != pick_list_item.batch_no:
				frappe.throw(f"Row: {item.idx} You can not change batch as pick list is already made.")
			
			delivered_qty = item.qty + pick_list_item.delivered_qty
			wastage_qty = item.wastage_qty + pick_list_item.wastage_qty
			
			if delivered_qty + wastage_qty > pick_list_item.qty:
				frappe.throw(f"Row {item.idx}: You can not deliver more than picked qty")
			
			frappe.db.set_value("Pick List Item", pick_list_item.name, 'delivered_qty', flt(delivered_qty))
			frappe.db.set_value("Pick List Item", pick_list_item.name, 'wastage_qty', flt(wastage_qty))

		if item.against_sales_order:
			sales_order_item = frappe.get_doc("Sales Order Item", item.so_detail)
			wastage_qty = item.wastage_qty + sales_order_item.wastage_qty
			delivered_qty = item.qty + sales_order_item.delivered_qty


			if delivered_qty + wastage_qty > sales_order_item.qty:
				frappe.throw(f"Row {item.idx}: You can not deliver more than sales order qty")
			
			frappe.db.set_value("Sales Order Item", sales_order_item.name, 'wastage_qty', flt(wastage_qty))

			if item.against_pick_list:
				frappe.db.set_value("Sales Order Item", sales_order_item.name, 'picked_qty', flt(sales_order_item.picked_qty - wastage_qty))

			update_sales_order_total_values(frappe.get_doc("Sales Order", item.against_sales_order))
		
		if not item.against_pick_list and item.against_sales_order:
			so_delivered_without_pick = frappe.db.get_value("Sales Order Item", item.so_detail, 'delivered_without_pick')
			frappe.db.set_value("Sales Order Item", item.so_detail, 'delivered_without_pick', so_delivered_without_pick + item.qty)
		
		if item.pl_detail:
			pick_list_batch_no = frappe.db.get_value("Pick List Item", item.pl_detail, 'batch_no')

			if item.batch_no != pick_list_batch_no:
				frappe.throw(_(f"Row: {item.idx} : Batch No {frappe.bold(item.batch_no)} is Not same as Pick List Batch No {frappe.bold(pick_list_batch_no)}."))

def update_status_pick_list(self):
	pick_list = list(set([item.against_pick_list for item in self.items if item.against_pick_list]))

	for pick in pick_list:
		pl = frappe.get_doc("Pick List", pick)
		delivered_qty = 0
		picked_qty = 0
		wastage_qty = 0

		for item in pl.locations:
			delivered_qty += item.delivered_qty
			wastage_qty += item.wastage_qty
			picked_qty += item.qty

		if picked_qty == 0:
			per_delivered = 100.0
		else:
			per_delivered = flt((delivered_qty / picked_qty) * 100)
		frappe.db.set_value("Pick List", pick, 'per_delivered', per_delivered)

def check_rate_qty(self):
	for item in self.items:
		if not item.rate or item.rate <= 0:
			frappe.throw(f"Row: {item.idx} Rate cannot be 0")
		if not item.qty or item.qty == 0:
			frappe.throw(f"Row: {item.idx} Quantity can not be 0 ")

@frappe.whitelist()
def create_delivery_note_from_pick_list(source_name, target_doc = None):
	def update_item_quantity(source, target, source_parent):
		target.qty = flt(source.qty) - flt(source.delivered_qty)
		target.stock_qty = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.conversion_factor)
	
	doc = get_mapped_doc('Pick List', source_name, {
		'Pick List': {
			'doctype': 'Delivery Note',
			'validation': {
				'docstatus': ['=', 1]
			}
		},
		'Sales Order Item': {
			'doctype': 'Delivery Note Item',
			'field_map': {
				'parent': 'sales_order',
				'name': 'sales_order_item'
			},
			'postprocess': update_item_quantity,
			'condition': lambda doc: abs(doc.delivered_qty) < abs(doc.qty) and doc.delivered_by_supplier!=1
		},
	}, target_doc)

	return doc

def wastage_stock_entry(self):
	flag = 0
	for row in self.items:
		if row.wastage_qty < 0:
			frappe.throw("Row {}: Please Don't Enter Negative Value in Wastage Qty".format(row.idx))
		elif row.wastage_qty > 0:
			flag = 1
			break
	if flag == 1:
		abbr = frappe.db.get_value('Company',self.company,'abbr')
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer"
		se.purpose = "Material Transfer"
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time
		se.set_posting_time = 1
		se.company = self.company
		se.reference_doctype = self.doctype
		se.reference_docname = self.name
		se.wastage = 1

		rejected_warehouse = frappe.db.get_value("Company", se.company, "default_rejected_warehouse")
		if not rejected_warehouse:
			frappe.throw("Please Define Rejected Warehouse in Company")

		for row in self.items:
			if row.wastage_qty > 0:
				se.append("items",{
					'item_code': row.item_code,
					'qty': row.wastage_qty,
					'basic_rate': row.rate,
					'batch_no': row.batch_no,
					's_warehouse': row.warehouse,
					't_warehouse': rejected_warehouse
				})

		se.save(ignore_permissions=True)
		se.submit()

def cancel_wastage_entry(self):
	if frappe.db.exists("Stock Entry",{'reference_doctype': self.doctype,'reference_docname':self.name}):
		se = frappe.get_doc("Stock Entry",{'reference_doctype': self.doctype,'reference_docname':self.name})
		se.flags.ignore_permissions = True
		if se.docstatus == 1:
			se.cancel()
		se.db_set('reference_doctype','')
		se.db_set('reference_docname','')
		se.delete()

@frappe.whitelist()
def get_rate_discounted_rate(item_code, customer, company, so_number = None):
	""" This function is use to get discounted rate and rate """
	item_group = frappe.get_value("Item", item_code, 'item_group')
	# parent_item_group = frappe.get_value("Item Group", item_group, 'parent_item_group')

	count = frappe.db.sql(f"""
		SELECT 
			COUNT(*) 
		FROM 
			`tabDelivery Note Item` as soi 
		JOIN 
			`tabDelivery Note` as so ON so.`name` = soi.`parent`
		WHERE 
			soi.`item_group` = '{item_group}' AND
			soi.`docstatus` = 1 AND
			so.customer = '{customer}' AND
			so.`company` = '{company}'
		LIMIT 1
	""")
	where_clause = ''
	if count[0][0]:
		where_clause = f"soi.item_group = '{item_group}' AND"
	
	data = None

	if so_number:
		data = frappe.db.sql(f"""
			SELECT 
				soi.`rate` as `rate`
			FROM 
				`tabDelivery Note Item` as soi 
			JOIN
				`tabDelivery Note` as so ON soi.parent = so.name
			WHERE
				{where_clause}
				so.`customer` = '{customer}' AND
				so.`company` = '{company}' AND
				so.`docstatus` != 2 AND
				so.`name` = '{so_number}'
			ORDER BY
				soi.`creation` DESC
			LIMIT 
				1
		""", as_dict = True)

	if not data:
		data = frappe.db.sql(f"""
			SELECT 
				soi.`rate` as `rate`
			FROM 
				`tabDelivery Note Item` as soi JOIN
				`tabDelivery Note` as so ON soi.parent = so.name
			WHERE
				{where_clause}
				so.`customer` = '{customer}' AND
				so.`company` = '{company}' AND
				so.`docstatus` != 2
			ORDER BY
				soi.`creation` DESC
			LIMIT 
				1
		""", as_dict = True)

	return data[0] if data else {'rate': 0}
