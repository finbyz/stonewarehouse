from __future__ import unicode_literals
from frappe import _

def get_data(data):
	data['fieldname'] = 'against_pick_list'
	data['transactions'] = [
		{
			'label': _('Sales Order'),
			'items': ['Sales Order']
		},
		{
			'label': _('Delivery Note'),
			'items': ['Delivery Note']
		},
	]

	data['internal_links'] = {
		'Sales Order': ['locations', 'sales_order'],
	}
	return data