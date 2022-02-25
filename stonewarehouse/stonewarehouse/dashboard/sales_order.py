from __future__ import unicode_literals
from frappe import _

def get_data(data):
	data['non_standard_fieldnames'] = {
		'Delivery Note': 'against_sales_order',
		'Auto Repeat': 'reference_document',
		'Pick List': 'sales_order'
	}

	data['transactions'] = [
		{
			'label': _('Fulfillment'),
			'items': ['Pick List', 'Delivery Note']
		},
		{
			'label': _('Purchasing'),
			'items': ['Material Request']
		},
		{
			'label': _('Manufacturing'),
			'items': ['Work Order']
		},
		{
			'label': _('Reference'),
			'items': ['Auto Repeat']
		}
	]

	return data
