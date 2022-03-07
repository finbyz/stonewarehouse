// Copyright (c) 2016, Finbyz Tech. Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["SO Delivery Status"] = {
	"filters": [
		{
			"label":"Sales Order",
			"fieldname":"name",
			"fieldtype":"Link",
			"options":"Sales Order"
		},
		{
			"label":"Company",
			"fieldname":"company",
			"fieldtype":"Link",
			"options":"Company"
		},			
		{
			"label":"Customer",
			"fieldname":"customer",
			"fieldtype":"Link",
			"options":"Customer"			
		},
		{
			"label":"Item Code",
			"fieldname":"item_code",
			"fieldtype":"Link",
			"options":"Item"			
		},
		{
			"label":"Ready To Dispatch",
			"fieldname":"ready_to_dispatch",
			"fieldtype":"Check"
		},
	]
};