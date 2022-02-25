import frappe, json
from frappe import _
from frappe.utils import today
from frappe.model.mapper import get_mapped_doc, map_child_doc, map_doc, map_fields
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as create_delivery_note_from_sales_order
from erpnext.stock.doctype.pick_list.pick_list import get_items_with_location_and_quantity
from frappe.utils import flt
from stonewarehouse.stonewarehouse.doc_events.sales_order import update_sales_order_total_values

def before_vaidate(self, method):
	remove_items_without_batch_no(self)
	update_remaining_qty(self)

def validate(self, method):
	check_item_qty(self)
	remove_items_without_batch_no(self)
	update_remaining_qty(self)

	for item in self.locations:
		if item.qty < 0:
			frappe.throw(f"Row: {item.idx} Quantity can not be negative.")

		ig = frappe.db.get_value("Item",item.item_code,'item_group')
		if ig != item.item_group:
			item.item_group = ig

def validate_sales_order(self):
	if self.sales_order:
		status = frappe.db.get_value("Sales Order",self.sales_order,"status")
		if status == "Closed" or status == "Cancelled":
			frappe.throw(_(f"Sales Order Cannot be cancelled or submitted"))

	for item in self.sales_order_item:
		if item.sales_order:
			status = frappe.db.get_value("Sales Order",item.sales_order,"status")
			if status == "Closed" or status == "Cancelled":
				frappe.throw(_(f"ROW: {item.idx} : Sales Order Cannot be cancelled or submitted"))

def before_submit(self, method):
	validate_sales_order(self)
	update_available_qty(self)
	update_remaining_qty(self)
	self.picked_sales_orders = []
	self.available_qty = []
	self.sales_order_item = []

def on_submit(self, method):
	check_item_qty(self)
	update_item_so_qty(self)
	update_sales_order(self, "submit")
	update_status_sales_order(self)

def before_update_after_submit(self,method):
	validate_item_qty(self)

def update_item_so_qty(self):
	from stonewarehouse.update_item import update_child_qty_rate
	for item in self.locations:
		doc = frappe.get_doc("Sales Order Item", item.sales_order_item)
		parent_doc = frappe.get_doc("Sales Order", item.sales_order)
		data = []

		for row in parent_doc.items:
			if row.name != item.sales_order_item:
				data.append({
					'docname': row.name,
					'name': row.name,
					'item_code': row.item_code,
					'qty': row.qty,
					'rate': row.rate
				})
			else:
				data.append({
					'docname': row.name,
					'name': row.name,
					'item_code': row.item_code,
					'qty': item.so_qty,
					'rate': row.rate
				})

		update_child_qty_rate("Sales Order", json.dumps(data), doc.parent)

def on_cancel(self, method):
	update_sales_order(self, "cancel")
	update_status_sales_order(self)
	
def check_item_qty(self):
	for item in self.available_qty:
		if item.remaining < 0:
			frappe.throw(f"Row {item.idx}: Remaining Qty Less than 0")

def validate_item_qty(self):
	for row in self.locations:
		if row.qty < flt(row.delivered_qty + row.wastage_qty):
			frappe.throw(f"Row {row.idx}: Qty can not be Less than delivered qty {flt(row.delivered_qty + row.wastage_qty)}")
		if row.qty > row.so_qty:
			frappe.throw(f"Row {row.idx}: Qty can not be greater than sales order qty {row.so_qty}")

def remove_items_without_batch_no(self):
	if self.locations:
		locations = [item for item in self.locations if item.batch_no]
		self.locations = locations

def update_delivered_percent(self):
	qty = 0
	delivered_qty = 0
	if self.locations:
		for index, item in enumerate(self.locations):
			qty += item.qty
			delivered_qty += item.delivered_qty

			item.db_set('idx', index + 1)

		try:
			self.db_set('per_delivered', (delivered_qty / qty) * 100)
		except:
			self.db_set('per_delivered', 0)

def update_available_qty(self):
	self.available_qty = []
	data = get_item_qty(self.company, self.item, self.customer, self.sales_order)
	for item in data:
		self.append('available_qty',{
			'item_code': item.item_code,
			'batch_no': item.batch_no,
			'lot_no': item.lot_no,
			'total_qty': item.total_qty,
			'picked_qty': item.picked_qty,
			'available_qty': item.available_qty,
			'remaining': item.available_qty,
			'picked_in_current': 0,
		})
	
	for i in self.available_qty:
		qty = 0
		for j in self.locations:
			if i.item_code == j.item_code and i.batch_no == j.batch_no:
				qty += j.qty
		i.picked_in_current = qty
		i.remaining -= qty

		if i.remaining < 0:
			frappe.throw(_(f"Remaining Qty Cannot be less than 0 ({i.remaining}) for item {i.item_code} and lot {i.lot_no}"))
	
def update_remaining_qty(self):
	sales_order_item_list = list(set([row.sales_order_item for row in self.locations]))

	for sales_order_item in sales_order_item_list:
		qty = 0
		for item in self.locations:
			if sales_order_item == item.sales_order_item:
				qty += flt(item.qty)
				item.remaining_qty = flt(item.so_qty) - flt(item.picked_qty) - flt(qty)

				if item.remaining_qty < 0:
					frappe.throw(_(f"ROW: {item.idx} : Remaining Qty Cannot be less than 0."))

def pick_qty_comment(sales_order,data):
	comment_so_doc = frappe.new_doc("Comment")
	comment_so_doc.comment_type = "Info"
	comment_so_doc.comment_email = frappe.session.user
	comment_so_doc.reference_doctype = "Sales Order"
	comment_so_doc.reference_name = sales_order

	comment_so_doc.content = data

	comment_so_doc.save()

def update_sales_order(self, method):
	if method == "submit":
		for item in self.locations:
			if frappe.db.exists("Sales Order Item", item.sales_order_item):
				so_qty, so_picked_qty, so_delivered_without_pick = frappe.db.get_value("Sales Order Item", item.sales_order_item, ['qty', 'picked_qty', 'delivered_without_pick'])
				picked_qty = so_picked_qty + item.qty + so_delivered_without_pick
				
				if picked_qty > so_qty:
					frappe.throw("Can not pick item {} in row {} more than {}".format(item.item_code, item.idx, item.qty - item.picked_qty))

				frappe.db.set_value("Sales Order Item", item.sales_order_item, 'picked_qty', picked_qty)
				
				if picked_qty > 0:
					pick_qty_comment(item.sales_order, f"Picked Qty {picked_qty} from item{item.item_code}")
			
			if item.sales_order:
				so = frappe.get_doc("Sales Order",item.sales_order)
				total_picked_qty = 0.0
				total_picked_weight = 0.0
				for row in so.items:
					row.db_set('picked_weight',flt(row.weight_per_unit * row.picked_qty))
					total_picked_qty += row.picked_qty
					total_picked_weight += row.picked_weight
				
				so.db_set('total_picked_qty', total_picked_qty)
				so.db_set('total_picked_weight', total_picked_weight)
	
	if method == "cancel":
		for item in self.locations:
			if frappe.db.exists("Sales Order Item", {'name': item.sales_order_item, 'parent': item.sales_order}):
				tile = frappe.get_doc("Sales Order Item", {'name': item.sales_order_item, 'parent': item.sales_order})
				picked_qty = tile.picked_qty - item.qty

				if tile.picked_qty < 0:
					frappe.throw("Row {}: All Item Already Canclled".format(item.idx))

				tile.db_set('picked_qty', picked_qty)

			if item.sales_order:
				so = frappe.get_doc("Sales Order",item.sales_order)
				total_picked_qty = 0.0
				total_picked_weight = 0.0
				for row in so.items:
					row.db_set('picked_weight',flt(row.weight_per_unit * row.picked_qty))
					total_picked_qty = row.picked_qty
					total_picked_weight += row.picked_weight
				
				so.db_set('total_picked_qty', total_picked_qty)
				so.db_set('total_picked_weight', total_picked_weight)
	
def update_status_sales_order(self):
	sales_order_list = list(set([item.sales_order for item in self.locations if item.sales_order]))

	for sales_order in sales_order_list:
		so = frappe.get_doc("Sales Order", sales_order)
		update_sales_order_total_values(so)
		qty = 0
		picked_qty = 0

		for item in so.items:
			qty += item.qty
			picked_qty += item.picked_qty

		so.db_set('per_picked', (picked_qty / qty) * 100)

@frappe.whitelist()
def get_item_qty(company, item_code = None, customer = None, sales_order = None):
	if not item_code and not customer and not sales_order:
		return
	
	batch_locations = []

	where_cond = ''
	if sales_order:
		where_cond = f" and soi.parent = '{sales_order}'"
	
	if customer:
		item_code_list = frappe.db.sql(f"""
			SELECT 
				DISTINCT soi.item_code
			FROM 
				`tabSales Order Item` as soi JOIN `tabSales Order` as so ON so.name = soi.parent
			WHERE
				so.docstatus = 1 AND
				so.customer = '{customer}' AND
				soi.qty != soi.picked_qty {where_cond} AND
				so.status != 'Closed'
		""")
		item_codes = [item[0] for item in item_code_list]
	
	if item_code and customer:
		if item_code not in item_codes:
			frappe.throw(_(f"Item {item_code} is not in sales order for Customer {customer}"))
	if sales_order:
		item_code_list = frappe.db.sql(f"""
			SELECT 
				DISTINCT soi.item_code
			FROM 
				`tabSales Order Item` as soi JOIN `tabSales Order` as so ON so.name = soi.parent
			WHERE
				so.docstatus = 1 AND
				soi.qty != soi.picked_qty {where_cond} AND
				so.status != 'Closed'
		""")
		# where_clause += f" AND so.name = '{sales_order}'"
		item_codes = [item[0] for item in item_code_list]
	
	if item_code:
		item_codes = [item_code]

	for item in item_codes:
		batch_locations += frappe.db.sql("""
			SELECT
				sle.`item_code`,
				sle.`batch_no`,
				batch.`lot_no`,
				SUM(sle.`actual_qty`) AS `actual_qty`
			FROM
				`tabStock Ledger Entry` sle, `tabBatch` batch
			WHERE
				sle.is_cancelled = 0 and sle.batch_no = batch.name
				and sle.`item_code`=%(item_code)s
				and sle.`company` = '{company}'
				and IFNULL(batch.`expiry_date`, '2200-01-01') > %(today)s
			GROUP BY
				`batch_no`,
				`item_code`
			HAVING `actual_qty` > 0
			ORDER BY IFNULL(batch.`expiry_date`, '2200-01-01'), batch.`creation`
		""".format(company=company), { #nosec
			'item_code': item,
			'today': today(),
		}, as_dict=1)
	
	for item in batch_locations:
		item['item_name'] = frappe.db.get_value('Item', item['item_code'], 'item_name')
		
		pick_list_available = frappe.db.sql(f"""
			SELECT SUM(pli.qty - (pli.delivered_qty + pli.wastage_qty)) FROM `tabPick List Item` as pli
			JOIN `tabPick List` AS pl ON pl.name = pli.parent
			WHERE pli.`item_code` = '{item['item_code']}'
			AND pli.`batch_no` = '{item['batch_no']}'
			AND pl.`docstatus` = 1
		""")

		item['picked_qty'] = (pick_list_available[0][0] or 0.0)
		item['to_pick_qty'] = item['available_qty'] = item['actual_qty'] - item['picked_qty']
		item['total_qty'] = item['actual_qty'] 

	return batch_locations

@frappe.whitelist()
def get_item_from_sales_order(company, item_code = None, customer = None, sales_order = None):
	if not item_code and not customer and not sales_order:
		return
	where_clause = ''
	where_cond = ''
	if sales_order:
		where_cond = f" and soi.parent = '{sales_order}'"
	sales_order_list = []

	if customer:
		item_code_list = frappe.db.sql(f"""
			SELECT 
				DISTINCT soi.item_code
			FROM 
				`tabSales Order Item` as soi JOIN `tabSales Order` as so ON so.name = soi.parent
			WHERE
				so.docstatus = 1 AND
				so.customer = '{customer}' AND
				soi.qty != soi.picked_qty {where_cond} AND
				so.status != 'Closed'
		""")
		where_clause += f" AND so.customer = '{customer}'"
		item_codes = [item[0] for item in item_code_list]
	
	if item_code and customer:
		if item_code not in item_codes:
			frappe.throw(_(f"Item {item_code} is not in sales order for Customer {customer}"))
	
	if sales_order:
		item_code_list = frappe.db.sql(f"""
			SELECT 
				DISTINCT soi.item_code
			FROM 
				`tabSales Order Item` as soi JOIN `tabSales Order` as so ON so.name = soi.parent
			WHERE
				so.docstatus = 1 AND
				soi.qty != soi.picked_qty {where_cond} AND
				so.status != 'Closed'
		""")
		where_clause += f" AND so.name = '{sales_order}'"
		item_codes = [item[0] for item in item_code_list]
	# frappe.throw(str(item_codes))
	
	if item_code and sales_order:
		if item_code not in item_codes:
			frappe.throw(_(f"Item {item_code} is not in sales order {sales_order}"))
	
	if item_code:
		item_codes = [item_code]
	
	for item in item_codes:
		sales_order_list += frappe.db.sql(f"""
			SELECT 
				so.name as sales_order, soi.delivered_without_pick, so.customer, so.transaction_date, so.delivery_date, soi.packing_type as packing_type, so.per_picked, so.order_item_priority, so.order_rank,
				soi.name as sales_order_item, soi.item_code, soi.picked_qty, soi.qty - soi.delivered_without_pick - soi.picked_qty as qty, soi.qty as so_qty, soi.uom, soi.stock_qty, soi.stock_uom, soi.conversion_factor
			FROM
				`tabSales Order Item` as soi JOIN 
				`tabSales Order`as so ON soi.parent = so.name 
			WHERE
				soi.item_code = '{item}' AND
				so.company = '{company}' AND
				so.`docstatus` = 1 {where_clause} AND
				soi.qty > soi.picked_qty AND
				so.status not in ('Closed','Completed','Cancelled','On Hold')
			ORDER BY
				soi.order_item_priority DESC
		""", as_dict = 1)

	return sales_order_list

@frappe.whitelist()
def get_pick_list_so(sales_order, item_code, sales_order_item):
	pick_list_list = frappe.db.sql(f"""
		SELECT 
			pli.sales_order, pli.sales_order_item, pli.customer, pli.name as pick_list_item, batch.packing_type,
			pli.date, pli.item_code, pli.qty, pli.qty - pli.delivered_qty - pli.wastage_qty as picked_qty, pli.delivered_qty, pli.wastage_qty,
			pli.delivered_qty, pli.batch_no,
			pli.lot_no, pli.uom, pli.stock_qty, pli.stock_uom,
			pli.conversion_factor, pli.name, pli.parent
		FROM
			`tabPick List Item` as pli
			JOIN `tabBatch` as batch on batch.name = pli.batch_no
		WHERE
			pli.item_code = '{item_code}' AND
			pli.sales_order = '{sales_order}' AND
			pli.sales_order_item = '{sales_order_item}' AND
			pli.`docstatus` = 1
	""", as_dict = 1)
	pick_list_list1 = []
	for item in pick_list_list:
		actual_qty = frappe.db.sql(f"""
			SELECT
				SUM(sle.`actual_qty`) AS `actual_qty`
			FROM
				`tabStock Ledger Entry` sle, `tabBatch` batch
			WHERE
				sle.is_cancelled = 0 and sle.batch_no = batch.name
				and sle.`item_code` = '{item_code}'
				and sle.batch_no = '{item.batch_no}'
			GROUP BY
				`batch_no`
			HAVING `actual_qty` > 0
		""")

		if actual_qty:
			actual_qty = actual_qty[0][0] or 0
		else:
			actual_qty = 0

		pick_list_available = frappe.db.sql(f"""
			SELECT SUM(pli.qty - (pli.delivered_qty + pli.wastage_qty)) FROM `tabPick List Item` as pli
			JOIN `tabPick List` AS pl ON pl.name = pli.parent
			WHERE `item_code` = '{item_code}'
			AND batch_no = '{item.batch_no}'
			AND pl.docstatus = 1
		""")

		if pick_list_available:
			pick_list_available = pick_list_available[0][0] or 0
		else:
			pick_list_available = 0

		# frappe.msgprint(str(actual_qty))
		# frappe.msgprint(str(pick_list_available))
		
		item.available_qty = actual_qty - pick_list_available + item.picked_qty
		item.actual_qty = actual_qty

		if item.qty > item.delivered_qty + item.wastage_qty:
			pick_list_list1.append(item)
		
	return pick_list_list

@frappe.whitelist()
def unpick_item_1(sales_order, sales_order_item = None, pick_list = None, pick_list_item = None, unpick_qty = None):
	try:
		unpick_item(sales_order, sales_order_item, pick_list, pick_list_item, unpick_qty)
	except:
		return "Error"


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

@frappe.whitelist()
def unpick_item(sales_order, sales_order_item = None, pick_list = None, pick_list_item = None, unpick_qty = None, sales_order_differnce_qty = 0.0):
	# if flt(unpick_qty) < 0:
	# 	frappe.throw(_("Unpick qty cannot be negative"))
	user = frappe.get_doc("User",frappe.session.user)
	role_list = [r.role for r in user.roles]

	if frappe.db.get_value("Sales Order",sales_order,'lock_picked_qty'):
		dispatch_person_user = frappe.db.get_value("Sales Person",frappe.db.get_value("Sales Order",sales_order,'dispatch_person'),'user')
		if dispatch_person_user:
			if user.name != dispatch_person_user and 'Local Admin' not in role_list and 'Sales Head' not in role_list:
				return "Only {} is allowed to unpick".format(dispatch_person_user)
	if pick_list_item and pick_list:
		unpick_qty = flt(unpick_qty)
		doc = frappe.get_doc("Pick List Item", pick_list_item)
		original_picked = doc.qty
		soi_doc = frappe.get_doc("Sales Order Item", sales_order_item)
		if not unpick_qty:
			diff_qty = doc.qty - doc.delivered_qty - flt(doc.wastage_qty)
			doc.db_set('qty', doc.qty - diff_qty)

			if diff_qty == 0:
				frappe.throw(_("You can not cancel this Sales Order, Delivery Note already there for this Sales Order."))

			picked_qty = frappe.db.get_value("Sales Order Item", doc.sales_order_item, 'picked_qty')
			soi_doc.db_set('picked_qty', flt(picked_qty) - flt(diff_qty))
			# frappe.db.set_value("Sales Order Item", doc.sales_order_item, 'picked_qty', (flt(picked_qty)- flt(diff_qty)))
		
			if not doc.delivered_qty and not doc.wastage_qty:
				doc.cancel()
				doc.delete()
			
			if diff_qty > 0:
				unpick_qty_comment(doc.parent, doc.sales_order, f"Unpicked Qty {diff_qty} / {original_picked} from item {doc.item_code}")
		else:
			if unpick_qty > 0 and unpick_qty > doc.qty - doc.wastage_qty - doc.delivered_qty:
				frappe.throw(f"You can not unpick qty {unpick_qty} higher than remaining pick qty { doc.qty - doc.wastage_qty - doc.delivered_qty }")
			elif unpick_qty < 0:
				actual_qty = frappe.db.sql(f"""
					SELECT
						SUM(sle.`actual_qty`) AS `actual_qty`
					FROM
						`tabStock Ledger Entry` sle, `tabBatch` batch
					WHERE
						sle.is_cancelled = 0 and sle.batch_no = batch.name
						and sle.`item_code` = '{soi_doc.item_code}'
						and sle.batch_no = '{doc.batch_no}'
					GROUP BY
						`batch_no`
					HAVING `actual_qty` > 0
				""")[0][0]

				pick_list_available = frappe.db.sql(f"""
					SELECT SUM(pli.qty - (pli.delivered_qty + pli.wastage_qty)) FROM `tabPick List Item` as pli
					JOIN `tabPick List` AS pl ON pl.name = pli.parent
					WHERE `item_code` = '{soi_doc.item_code}'
					AND batch_no = '{doc.batch_no}'
					AND pl.docstatus = 1
				""")[0][0] or 0
				
				available_qty = actual_qty - pick_list_available + doc.qty
				
				if available_qty < doc.qty - unpick_qty:
					frappe.throw(f"Qty can not be greater than available qty {available_qty} in Lot {doc.lot_no}")
				original_picked = doc.qty
				doc.db_set('qty', doc.qty - unpick_qty)
				soi_doc.db_set('picked_qty', flt(soi_doc.picked_qty) - flt(unpick_qty))
				if unpick_qty > 0:
					unpick_qty_comment(doc.parent, doc.sales_order, f"Unpicked Qty {unpick_qty} / {original_picked} from item {doc.item_code}")
			else:
				original_picked = doc.qty
				doc.db_set('qty', doc.qty - unpick_qty)
				soi_doc.db_set('picked_qty', flt(soi_doc.picked_qty) - flt(unpick_qty))
				if unpick_qty > 0:
					unpick_qty_comment(doc.parent, doc.sales_order, f"Unpicked Qty {unpick_qty} / {original_picked} from item {doc.item_code}")

		
		update_delivered_percent(frappe.get_doc("Pick List", doc.parent))
		update_sales_order_total_values(frappe.get_doc("Sales Order", doc.sales_order))
		
	elif sales_order and sales_order_item:
		data = frappe.get_all("Pick List Item", {'sales_order': sales_order, 'sales_order_item': sales_order_item, 'docstatus': 1}, ['name'])
		if sales_order_differnce_qty:
			
			for pl in data:
				if not sales_order_differnce_qty:
					break
				doc = frappe.get_doc("Pick List Item", pl.name)
				original_picked = doc.qty
				soi_doc = frappe.get_doc("Sales Order Item", doc.sales_order_item)
				diff_qty = flt(doc.qty) - flt(doc.delivered_qty) - flt(doc.wastage_qty)
				
				if sales_order_differnce_qty >= diff_qty:
					sales_order_differnce_qty -= diff_qty
				else:
					diff_qty = sales_order_differnce_qty
					sales_order_differnce_qty = 0
				
				doc.db_set('qty', doc.qty - diff_qty)

				picked_qty = frappe.db.get_value("Sales Order Item", doc.sales_order_item, 'picked_qty')
				#soi_doc.db_set('picked_qty', flt(picked_qty) - flt(diff_qty))
								
				if not unpick_qty:
					if not doc.delivered_qty and not doc.wastage_qty and not doc.qty:
						if doc.docstatus == 1:
							doc.cancel()
						doc.delete()
				
				if diff_qty > 0:
					unpick_qty_comment(doc.parent, doc.sales_order, f"Unpicked Qty {diff_qty} / {original_picked} from item {doc.item_code}")
				
				update_delivered_percent(frappe.get_doc("Pick List", doc.parent))
				# update_sales_order_total_values(frappe.get_doc("Sales Order", doc.sales_order))
		else:
			for pl in data:
				doc = frappe.get_doc("Pick List Item", pl.name)
				original_picked = doc.qty
				soi_doc = frappe.get_doc("Sales Order Item", doc.sales_order_item)
				diff_qty = flt(doc.qty) - flt(doc.delivered_qty) - flt(doc.wastage_qty)
				doc.db_set('qty', doc.qty - diff_qty)

				picked_qty = frappe.db.get_value("Sales Order Item", doc.sales_order_item, 'picked_qty')
				
				soi_doc.db_set('picked_qty', flt(picked_qty) - flt(diff_qty))
				
				if not unpick_qty:
					if not doc.delivered_qty and not doc.wastage_qty:
						if doc.docstatus == 1:
							doc.cancel()
						doc.delete()
				
				if diff_qty > 0:
					unpick_qty_comment(doc.parent, doc.sales_order, f"Unpicked Qty {diff_qty} / {original_picked} from item {doc.item_code}")
				
				update_delivered_percent(frappe.get_doc("Pick List", doc.parent))
				update_sales_order_total_values(frappe.get_doc("Sales Order", doc.sales_order))
		
	else:
		data = frappe.get_all("Pick List Item", {'sales_order': sales_order, 'docstatus': 1}, ['name'])
		for pl in data:
			doc = frappe.get_doc("Pick List Item", pl.name)
			soi_doc = frappe.get_doc("Sales Order Item", doc.sales_order_item)
			original_picked = doc.qty
			diff_qty = doc.qty - doc.delivered_qty - flt(doc.wastage_qty)
			doc.db_set('qty', doc.qty - diff_qty)

			picked_qty = frappe.db.get_value("Sales Order Item", doc.sales_order_item, 'picked_qty')
			soi_doc.db_set('picked_qty', flt(picked_qty) - flt(diff_qty))
			# frappe.db.set_value("Sales Order Item", doc.sales_order_item, 'picked_qty', flt(picked_qty) - flt(diff_qty))

			if not unpick_qty:
				if not doc.delivered_qty and not doc.wastage_qty:
					if doc.docstatus == 1:
						doc.cancel()
					
					doc.delete()
			
			if diff_qty > 0:
				unpick_qty_comment(doc.parent, doc.sales_order, f"Unpicked Qty {diff_qty} / {original_picked} from item {doc.item_code}")
			
			update_delivered_percent(frappe.get_doc("Pick List", doc.parent))
		
		update_sales_order_total_values(frappe.get_doc("Sales Order", sales_order))
		
	return "Pick List to this Sales Order Have Been Deleted."

@frappe.whitelist()
def unpick_picked_qty_sales_order(sales_order, sales_order_item, item_code):
	unpick_item(sales_order, sales_order_item = sales_order_item)
	correct_picked_qty(sales_order)

@frappe.whitelist()
def correct_picked_qty(sales_order):
	so=frappe.get_doc("Sales Order",sales_order)

	for item in so.items:
		picked_qty = flt(frappe.db.get_value("Pick List Item", {'sales_order': sales_order, 'sales_order_item': item.name, 'docstatus': 1, 'item_code':item.item_code},'sum(qty - wastage_qty)'))
		soi_doc = frappe.get_doc("Sales Order Item", item.name)
		soi_doc.db_set('picked_qty', picked_qty)
	
	update_sales_order_total_values(frappe.get_doc("Sales Order", sales_order))

	return "Pick List to this Sales Order Has been Corrected."
	
@frappe.whitelist()
def get_items(filters):
	from six import string_types
	import json

	if isinstance(filters, string_types):
		filters = json.loads(filters)

	batch_locations = frappe.db.sql("""
		SELECT
			sle.`item_code`,
			sle.`batch_no`,
			batch.lot_no,
			batch.packing_type,
			SUM(sle.`actual_qty`) AS `actual_qty`
		FROM
			`tabStock Ledger Entry` sle, `tabBatch` batch
		WHERE
			sle.is_cancelled = 0 and sle.batch_no = batch.name
			and sle.`item_code`=%(item_code)s
			and sle.`company` = '{company}'
			and IFNULL(batch.`expiry_date`, '2200-01-01') > %(today)s
		GROUP BY
			`batch_no`,
			`item_code`
		HAVING `actual_qty` > 0
		ORDER BY IFNULL(batch.`expiry_date`, '2200-01-01'), batch.`creation`
	""".format(company=filters['company']), { #nosec
		'item_code': filters['item_code'],
		'today': today(),
	}, as_dict=1)

	item_name = frappe.db.get_value('Item', filters['item_code'], 'item_name')
	
	data = []
	for item in batch_locations:
		item['item_name'] = item_name
		
		pick_list_available = frappe.db.sql(f"""
			SELECT SUM(pli.qty - (pli.delivered_qty + pli.wastage_qty)) FROM `tabPick List Item` as pli
			JOIN `tabPick List` AS pl ON pl.name = pli.parent
			WHERE `item_code` = '{filters['item_code']}'
			AND batch_no = '{item['batch_no']}'
			AND pl.docstatus = 1
		""")
		
		item['picked_qty'] = flt(pick_list_available[0][0] or 0.0)
		item['available_qty'] = flt(item['actual_qty'] - (pick_list_available[0][0] or 0.0))
		item['to_pick_qty'] = str(min(flt(item['available_qty']), flt(filters['to_pick_qty'])))
		if item['available_qty'] <= 0.0:
			item = None

		if item:
			data.append(item)
	# frappe.msgprint(str(data))
	return data

@frappe.whitelist()
def get_sales_order_items(sales_order):
	doc = frappe.get_doc("Sales Order", sales_order)

	items = []
	for item in doc.items:
		items.append({
			'sales_order': doc.name,
			'sales_order_item': item.name,
			'qty': item.qty - item.wastage_qty - item.delivered_qty,
			'item_code': item.item_code,
			'rate': item.rate,
			'picked_qty': item.picked_qty + item.delivered_without_pick - item.delivered_qty,
			'delivered_qty': item.delivered_qty,
			'wastage_qty': item.wastage_qty,
			'packing_type': item.packing_type,
			'order_rank': doc.order_rank,
			'delivered_without_pick': item.delivered_without_pick
		})
	return items

@frappe.whitelist()
def update_pick_list(items):
	picked_items = json.loads(items)
	for item in picked_items:
		pick_list_item_doc = frappe.get_doc("Pick List Item", item['pick_list_item'])

		picked_qty_old = pick_list_item_doc.qty
		diff_qty = picked_qty_old - flt(item['picked_qty'])
		
		if diff_qty:
			unpick_item(pick_list_item_doc.sales_order, sales_order_item = pick_list_item_doc.sales_order_item, pick_list = pick_list_item_doc.parent, pick_list_item = pick_list_item_doc.name, unpick_qty = diff_qty)

	return 'success'