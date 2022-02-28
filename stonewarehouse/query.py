import frappe
from frappe import _
from frappe.desk.reportview import get_match_cond
from six import string_types
import json
from erpnext.controllers.queries import get_doctype_wise_filters
from frappe.desk.reportview import get_match_cond, get_filters_cond

@frappe.whitelist()
def get_warehouse(doctype, txt, searchfield, start, page_len, filters):
	cond = ""

	meta = frappe.get_meta("Warehouse")
	searchfield = meta.get_search_fields()

	searchfields = " or ".join(["batch." + field + " like %(txt)s" for field in searchfield])

	if filters.get("batch_no"):
		cond += " and (sle.batch_no = %(batch_no)s) "
	
	if filters.get("company"):
		cond += " and (sle.company = %(company)s) "
	
	if filters.get("item_code"):
		cond += " and (sle.item_code = %(item_code)s) "
	
	args = {
		'item_code': filters.get("item_code"),
		'batch_no': filters.get("batch_no"),
		'txt': "%{0}%".format(txt),
		"start": start,
		"page_len": page_len
	}

	w_query = frappe.db.sql("""select sle.warehouse, batch.lot_no, round(sum(sle.actual_qty),2), sle.stock_uom
		from `tabStock Ledger Entry` sle
			INNER JOIN `tabBatch` batch on sle.batch_no = batch.name
		where
			sle.item_code = %(item_code)s
			and batch.docstatus < 2
			and (sle.warehouse like %(txt)s or {searchfields})
			{0}
		group by warehouse having sum(sle.actual_qty) > 0
		order by batch.expiry_date, sle.batch_no desc
		limit %(start)s, %(page_len)s""".format(cond, searchfields=searchfields), args)
	
	return w_query

@frappe.whitelist()
def get_batch_no(doctype, txt, searchfield, start, page_len, filters):
	cond = ""

	meta = frappe.get_meta("Batch")
	searchfield = meta.get_search_fields()

	searchfields = " or ".join(["batch." + field + " like %(txt)s" for field in searchfield])

	if filters.get("posting_date"):
		cond = "and (batch.expiry_date is null or batch.expiry_date >= %(posting_date)s)"
		
	if filters.get("customer"):
		cond = "and (batch.customer = %(customer)s or ifnull(batch.customer, '') = '') "

	batch_nos = None
	args = {
		'item_code': filters.get("item_code"),
		'warehouse': filters.get("warehouse"),
		'posting_date': filters.get('posting_date'),
		'txt': "%{0}%".format(txt),
		"start": start,
		"page_len": page_len
	}

	if args.get('warehouse'):
		batch_nos = frappe.db.sql("""select sle.batch_no, batch.lot_no, round(sum(sle.actual_qty),2), sle.stock_uom
				from `tabStock Ledger Entry` sle
					INNER JOIN `tabBatch` batch on sle.batch_no = batch.name
				where
					sle.item_code = %(item_code)s
					and sle.warehouse = %(warehouse)s
					and batch.docstatus < 2
					and (sle.batch_no like %(txt)s or {searchfields})
					{0}
					{match_conditions}
				group by batch_no having sum(sle.actual_qty) > 0
				order by batch.expiry_date, sle.batch_no desc
				limit %(start)s, %(page_len)s""".format(cond, match_conditions=get_match_cond(doctype), searchfields=searchfields), args)

	if batch_nos:
		return batch_nos
	else:
		return frappe.db.sql("""select batch.name, batch.lot_no, batch.expiry_date, sle.batch_no, batch.lot_no, round(sum(sle.actual_qty),2), sle.stock_uom from `tabBatch` batch
			JOIN `tabStock Ledger Entry` sle on sle.batch_no = batch.name
			where batch.item = %(item_code)s
			and batch.docstatus < 2
			and (sle.batch_no like %(txt)s or {searchfields})
			{0}
			{match_conditions} AND
			sle.company = '{company}'
			group by sle.batch_no having sum(sle.actual_qty) > 0
			order by batch.expiry_date, batch.name desc
			limit %(start)s, %(page_len)s""".format(cond, match_conditions=get_match_cond(doctype), company=filters.get('company'), searchfields=searchfields), args)

def set_batches(self, warehouse_field):
	if self._action == 'submit':
		for row in self.items:
			if not row.get(warehouse_field):
				continue

			has_batch_no = frappe.db.get_value('Item', row.item_code, 'has_batch_no')
			
			if has_batch_no:
				if not row.get('lot_no'):
					frappe.throw(_("Please set Lot No in row {}".format(row.idx)))

				batch_no = get_batch(row.as_dict())

				if batch_no:
					row.batch_no = batch_no

			elif row.lot_no:
				frappe.throw(_("Please clear Lot No for Item {} as it is not batch wise item in row {}".format(row.item_code, row.idx)))

@frappe.whitelist()
def get_batch(args):
	"""
	Returns the batch according to Item Code, Merge and Grade
		args = {
			"item_code": "",
			"lot_no": "",
		}
	"""
	def process_args(args):
		if isinstance(args, string_types):
			args = json.loads(args)

		args = frappe._dict(args)
		return args

	def validate_args(args):
		if not args.item_code:
			frappe.throw(_("Please specify Item Code"))

		elif not args.lot_no:
			frappe.throw(_("Please specify Lot NO"))

	args = process_args(args)

	validate_args(args)

	batch_nos = frappe.db.sql_list(""" select name from `tabBatch` 
		where lot_no = %s and item = %s """, (args.lot_no,args.item_code))

	batch_no = None
	if batch_nos:
		batch_no = batch_nos[0]

	return batch_no
			
@frappe.whitelist()
def warehouse_query(doctype, txt, searchfield, start, page_len, filters):
	# Should be used when item code is passed in filters.
	conditions, bin_conditions = [], []
	filter_dict = get_doctype_wise_filters(filters)

	sub_query = """ select round(`tabBin`.actual_qty, 2) from `tabBin`
		where `tabBin`.warehouse = `tabWarehouse`.name
		{bin_conditions} """.format(
		bin_conditions=get_filters_cond(doctype, filter_dict.get("Bin"),
			bin_conditions, ignore_permissions=True))

	query = """select `tabWarehouse`.name,
		CONCAT_WS(" : ", "Actual Qty", ifnull( ({sub_query}), 0) ) as actual_qty
			from `tabWarehouse`
		where
		   `tabWarehouse`.`{key}` like {txt}
			{fcond} {mcond}
		having
			ifnull( ({sub_query}), 0) > 0.0
		order by
			`tabWarehouse`.name desc
		
		limit
			{start}, {page_len}
		""".format(
			sub_query=sub_query,
			key=searchfield,
			fcond=get_filters_cond(doctype, filter_dict.get("Warehouse"), conditions),
			mcond=get_match_cond(doctype),
			start=start,
			page_len=page_len,
			txt=frappe.db.escape('%{0}%'.format(txt))
		)

	return frappe.db.sql(query)

@frappe.whitelist()	
def sales_order_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []

	so_searchfield = frappe.get_meta("Sales Order").get_search_fields()
	so_searchfields = " or ".join(["so.`" + field + "` like %(txt)s" for field in so_searchfield])

	soi_searchfield = frappe.get_meta("Sales Order Item").get_search_fields()
	soi_searchfield += ["item_code"]
	soi_searchfields = " or ".join(["soi.`" + field + "` like %(txt)s" for field in soi_searchfield])

	searchfield = so_searchfields + " or " + soi_searchfields

	where_condition = ''
	if filters.get("item_code"):
		where_condition += " and soi.item_code = '{}'".format(filters.get("item_code"))
	
	if filters.get("customer"):
		where_condition += " and so.customer = '{}'".format(filters.get("customer"))

	return frappe.db.sql("""select so.name, so.status, so.transaction_date, so.customer, soi.item_code
			from `tabSales Order` so
		RIGHT JOIN `tabSales Order Item` soi ON (so.name = soi.parent)
		where so.docstatus = 1
			and so.status != "Closed" {where_condition}
			and ({searchfield})
			and so.company = '{company}'
		order by
			if(locate(%(_txt)s, so.name), locate(%(_txt)s, so.name), 99999)
		limit %(start)s, %(page_len)s """.format(searchfield=searchfield, where_condition = where_condition, company = filters.get("company")), {
			'txt': '%%%s%%' % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
			'item_code': filters.get('item_code'),
			'customer': filters.get('customer')
		})