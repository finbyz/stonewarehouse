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
