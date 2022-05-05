import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, format_time, floor
from erpnext.stock.doctype.pick_list.pick_list import PickList

# @frappe.whitelist()
# def set_item_locations(self):
# 	pass

class CustomPickList(PickList):
	@frappe.whitelist()
	def set_item_locations(self, save=False):
		return

	def before_submit(self):
		for item in self.locations:
			# if the user has not entered any picked qty, set it to stock_qty, before submit
			# if item.picked_qty == 0:
			# 	item.picked_qty = item.stock_qty

			# if item.sales_order_item:
			# 	# update the picked_qty in SO Item
			# 	self.update_so(item.sales_order_item, item.picked_qty, item.item_code)

			if not frappe.get_cached_value("Item", item.item_code, "has_serial_no"):
				continue
			if not item.serial_no:
				frappe.throw(
					_("Row #{0}: {1} does not have any available serial numbers in {2}").format(
						frappe.bold(item.idx), frappe.bold(item.item_code), frappe.bold(item.warehouse)
					),
					title=_("Serial Nos Required"),
				)
			if len(item.serial_no.split("\n")) == item.picked_qty:
				continue
			frappe.throw(
				_(
					"For item {0} at row {1}, count of serial numbers does not match with the picked quantity"
				).format(frappe.bold(item.item_code), frappe.bold(item.idx)),
				title=_("Quantity Mismatch"),
			)
