// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Batch-Wise Balance"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"width": "80",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "MultiSelectList",
			"get_data": function (text) {
				//if (!frappe.query_report.item_group) return;
				return frappe.db.get_link_options('Item Group', text)
			},
			"change": function () {
				frappe.query_report.refresh();
			}
		},
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "MultiSelectList",
			"get_data": function (text) {
				//if (!frappe.query_report.item_group) return;
				return frappe.db.get_link_options('Item', text, filters = { 'has_batch_no': 1 })
			},
			"change": function () {
				frappe.query_report.refresh();
			},
		},
		{
			"fieldname": "not_in_item_code",
			"label": __("Not in Item Code"),
			"fieldtype": "MultiSelectList",
			"get_data": function (text) {
				//if (!frappe.query_report.item_group) return;
				return frappe.db.get_link_options('Item', text, filters = { 'has_batch_no': 1 })
			},
			"change": function () {
				frappe.query_report.refresh();
			},
		},
		{
			"fieldname": "print_with_picked_qty",
			"label": __("Print With Picked Qty"),
			"fieldtype": "Check",
		},
		{
			"fieldname": "print_with_unlocked_qty",
			"label": __("Print With Unlocked Qty"),
			"fieldtype": "Check",
		},
		{
			"fieldname": "sales_order",
			"label": __("Sales Order"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"get_query": function() {
				var company = frappe.query_report.get_filter_value('company');
				return {
					"doctype": "Sales Order",
					"filters": {
						"company": ['in', company],
						"docstatus": 1,
						"per_delivered": ['!=', 100],
						"status": ['not in', ('Draft', 'Submitted', 'Closed')]
					}
				}
			}
		},
		{
			"fieldname": "warehouse",
			"label": __("Show Warehouse"),
			"fieldtype": "Check",
			"default":1
		},
	]
}


function get_picked_item_details(item_code, batch_no, company, from_date, to_date, bal_qty, total_picked_qty, total_remaining_qty) {
	let template = `
		<table class="table table-borderless" style="border: 0 !important; font-size:95%;">
			<tr style="border: 0 !important;">
				<td style="border: 0 !important;"><b>Batch No: </b> {{ data[0]['batch_no'] }}</td>
				<td style="border: 0 !important;"><b>Picked Qty: </b> {{ data[0]['total_picked_qty'] }}</td>
			</tr>
			<tr style="border: 0 !important;">
				<td style="border: 0 !important;"><b>Qty: </b> {{ data[0]['bal_qty'] }}</td>
				<td style="border: 0 !important;"><b>Available Qty: </b> {{ data[0]['total_remaining_qty'] }}</td>
			</tr>
			<tr style="border: 0 !important;">
				<td style="border: 0 !important;"></td>
				<td style="border: 0 !important;"><b>Unlocked Qty: </b>{{ data[data.length-1].unlocked_qty }} </td>
			</tr>
		</table>
		{% if data[0]['customer'] %}
		<table class="table table-bordered" style="margin: 0; font-size:80%; width:700px;align:center">
			<thead>
				<th>{{ __("Customer") }}</th>
				<th>{{ __("Lock Pick Qty") }}</th>
				<th>{{ __("Sales Order") }}</th>
				<th>{{ __("Delivery Date") }}</th>
				<th>{{ __("Pick List") }}</th>
				<th>{{ __("% Picked") }}</th>
				<th>{{ __("Picked") }}</th>
				<th>{{ __("Unpick Qty") }}</th>
				<th></th>
			</thead>
			<tbody>
				
				{% for (let row of data ) { %}
				
					<tr class="{{ __(row['pick_list_item']) }}">
						<td>{{ __(row['customer']) }}</td>
						<td>{{ __(row['lock_picked_qty']) }}</td>
						<td>{{ __(row['sales_order_link']) }}</td>
						<td>{{ __(row['date']) }}</td>
						<td>{{ __(row['pick_list_link']) }}</td>
						<td>{{ __(frappe.format(row['per_picked'], {'fieldtype': 'Percent'})) }}</td>
						<td>{{ __(row['picked_qty']) }}</td>
						<td><input type="float"  min="0" onkeypress="return (event.charCode == 8 || event.charCode == 0 || event.charCode == 46) ? null : event.charCode >= 48 && event.charCode <= 57" style="width:30px" id="{{ row['pick_list_item'] }}"></input></td>
						<td><button style="margin-left:5px;border:none;color: #fff; background-color: red; padding: 3px 5px;border-radius: 5px;" type="button" sales-order="{{ __(row['sales_order']) }}" sales-order-item="{{ __(row['sales_order_item']) }}" pick-list="{{ __(row['pick_list']) }}" pick-list-item="{{ __(row['pick_list_item']) }}" onClick=remove_picked_item_batch_wise(this.getAttribute("sales-order"),this.getAttribute("sales-order-item"),this.getAttribute("pick-list"),this.getAttribute("pick-list-item"),document.getElementById("{{ row['pick_list_item'] }}").value)>Unpick</button></td>
					</tr>
				{% } %}
			</tbody>
		</table>
		{% endif %}`;
// onkeypress="return (event.charCode == 8 || event.charCode == 0 || event.charCode == 13) ? null : event.charCode >= 48 && event.charCode <= 57"
	// docudocument.getElementById("demo").innerHTML = item_code;

	frappe.call({
		method: "stonewarehouse.stonewarehouse.report.batch_wise_balance.batch_wise_balance.get_picked_item",
		args: {
			item_code: item_code,
			batch_no: batch_no,
			from_date: from_date,
			to_date: to_date,
			company: company,
			bal_qty: bal_qty,
			total_picked_qty: total_picked_qty,
			total_remaining_qty: total_remaining_qty,
		},
		callback: function (r) {
			let message = frappe.template.compile(template)({ 'data': r.message });
			frappe.msgprint({
				message: message,
				title: "Batch-Wise Balance Details : " + item_code,
			});
			$(frappe.msg_dialog.wrapper).addClass("modal-lg");
		}
	})
}

function remove_picked_item_batch_wise(sales_order, sales_order_item, pick_list, pick_list_item, unpick_qty) {
	frappe.call({
		method: "stonewarehouse.stonewarehouse.doc_events.pick_list.unpick_item",
		args: {
			sales_order: sales_order,
			sales_order_item: sales_order_item,
			pick_list: pick_list,
			pick_list_item: pick_list_item,
			unpick_qty:unpick_qty
		},
		callback: function (r) {
			if(r.message){
				$(".modal").modal('hide');
				setTimeout(function(){frappe.msgprint(r.message)}, 500);
			}
			$('.' + pick_list_item).hide()
		}
	})
}
