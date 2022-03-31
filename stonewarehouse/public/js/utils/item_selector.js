ItemSelector = Class.extend({
	init: function (opts) {
		$.extend(this, opts);
		this.setup();
	},

	setup: function(){
		this.item_locations_data = []
		this.make_dialog();
	},
	
	make_dialog: function(){
		var me = this;
		this.data = [];

		var fields = 
		[
			{
				label: __('Item Code'),
				fieldtype:'Link',
				fieldname: 'item_code',
				options: 'Item',
				read_only: 1,
				reqd: 1,
				default: me.item_code,
			},
			{
				label: __('Customer'),
				fieldtype:'Link',
				options:'Customer',
				fieldname: 'customer',
				read_only: 1,
				reqd: 1,
				default: me.customer,
			},
			{
				label: __('Idx'),
				fieldtype:'Int',
				fieldname: 'idx',
				read_only: 1,
				reqd: 1,
				hidden: 1,
				default: me.idx,
			},	
			{fieldtype:'Column Break'},
			{
				label: __('Sales Order'),
				fieldtype:'Link',
				fieldname: 'sales_order',
				options: 'Sales Order',
				reqd: 1,
				read_only: 1,
				default: me.sales_order
			},
			{
				label: __('Sales Order Date'),
				fieldtype:'Date',
				fieldname: 'so_date',
				read_only: 1,
				reqd: 1,
				default: me.date,
			},
			{
				label: __('Sales Order Item'),
				fieldtype:'Data',
				fieldname: 'sales_order_item',
				reqd: 0,
				read_only: 1,
				hidden: 1,
				default: me.sales_order_item
			},
			{
				label: __('SO Picked %'),
				fieldtype:'Percent',
				fieldname: 'so_picked_percent',
				reqd: 0,
				read_only: 1,
				default: me.so_picked_percent
			},
			{ fieldtype: 'Section Break', label: __('Quantity') },
			{
				label: __('Sales Order Qty'),
				fieldtype:'Float',
				fieldname: 'so_qty',
				reqd: 0,
				default: me.so_qty,
				read_only: 0,
				change: function(){
					var previously_picked = this.layout.get_value('previously_picked') || 0;
					var picked_qty = this.layout.get_value('picked_qty') || 0;
					var so_qty = this.layout.get_value('so_qty') || 0;
					cur_dialog.set_value('remaining_to_pick', (so_qty - previously_picked - picked_qty - (me.so_delivered_without_pick || 0)));
				}
			},
			{
				label: __('Previously Picked'),
				fieldtype:'Float',
				fieldname: 'previously_picked',
				reqd: 0,
				default: me.picked_qty,
				read_only: 1,
				hidden: 1,
			},
			{fieldtype:'Column Break'},
			{
				label: __('Previously Picked'),
				fieldtype:'Float',
				fieldname: 'previously_picked_qty',
				reqd: 0,
				default: me.picked_qty,
				read_only: 1
			},
			{fieldtype:'Column Break'},
			{
				label: __('Picked Qty'),
				fieldtype:'Float',
				fieldname: 'picked_qty',
				default: '0',
				reqd: 0,
				read_only: 1,
				change: function(){
					var previously_picked = this.layout.get_value('previously_picked') || 0;
					var picked_qty = this.layout.get_value('picked_qty') || 0;
					var so_qty = this.layout.get_value('so_qty') || 0;
					cur_dialog.set_value('remaining_to_pick', (so_qty - previously_picked - picked_qty - (me.delivered_without_pick || 0)));
				}
			},
			{
				label: __('Remaining to Pick Qty'),
				fieldtype:'Float',
				fieldname: 'remaining_to_pick',
				default: me.remaining_to_pick,
				reqd: 0,
				read_only: 1,
				change: function(){
					me.set_item_qty()
				}
			}
		]

		fields = fields.concat(this.get_item_fields());

		me.dialog = new frappe.ui.Dialog({
			title: __("Add Items"),
			fields: fields,
		});

		me.dialog.set_primary_action(__("Add"), function(){
			me.values = me.dialog.get_values();

			var picked_qty = me.values.picked_qty + me.picked_qty
			var so_qty = flt(me.values.so_qty)
			if (picked_qty == 0){
				me.dialog.hide();
			}
			else if (so_qty >= picked_qty){
				me.set_item_locations_in_frm();
				me.dialog.hide();
			} else {
				frappe.msgprint("Picked Qty should be less than " + (so_qty - me.picked_qty))
			}
		});

		var $package_wrapper = this.get_item_location_wrapper();

		$($package_wrapper).find('.grid-remove-rows .grid-delete-rows').click(function (event) {
			dialog(this);
			event.preventDefault();
			event.stopPropagation();
			return false;
	 });
		// $($package_wrapper).find('.grid-add-row').hide();

		me.dialog.show();
		var filters = {'item_code': me.item_code};
		me.get_items(filters);

		this.bind_events();
	},
	get_items: function(filters) {
		var me = this;
		var item_locations = me.dialog.fields_dict.item_locations;
		if(!filters['item_code']){
			item_locations.grid.df.data = [];
			item_locations.grid.refresh();
			return;
		}

		filters['company'] = me.company;
		filters['to_pick_qty'] = me.remaining_to_pick

		frappe.call({
			method: "stonewarehouse.stonewarehouse.doc_events.pick_list.get_items",
			freeze: true,
			args: {
				'filters': filters,
			},
			callback: function(r){
				item_locations.grid.df.data = []
				r.message.forEach(value => {
					me.frm.doc.available_qty.forEach(element => {
						if (value.batch_no == element.batch_no){
							value.available_qty = value.available_qty - (element.picked_in_current || 0)
						}
					});
					setTimeout(function(){},2000)
					if (me.batch_no && value.batch_no == me.batch_no){
						value.available_qty = value.available_qty + me.qty
					}
					value.to_pick_qty = Math.min(me.dialog.fields_dict.remaining_to_pick.value, value.available_qty)
					item_locations.grid.df.data.push(value)
					item_locations.grid.refresh();
				});

				// item_locations.grid.df.data = r.message;
				item_locations.grid.refresh();
				// me.set_item_location_data();
			},
		});
	},
	get_item_fields: function(){
		var me = this;

		return [
			{fieldtype:'Section Break', label: __('Item Location Details')},
			{
				label: __("Item"),
				fieldname: 'item_locations',
				fieldtype: "Table",
				read_only: 0,
				fields:[
					{
						'label': 'Item Code',
						'fieldtype': 'Link',
						'fieldname': 'item_code',
						'options': 'Item',
						'read_only': 1,
					},
					{
						'label': 'Item Name',
						'fieldtype': 'Data',
						'fieldname': 'item_name',
						'read_only': 1,
					},
					{
						'label': 'Batch No',
						'fieldtype': 'Link',
						'fieldname': 'batch_no',
						'options': 'Batch',
						'read_only': 1,
						'in_list_view': 1
					},				
					{
						'label': 'To Pick',
						'fieldtype': 'Float',
						'fieldname': 'to_pick_qty',
						'in_list_view': 1,
						'columns': 2,
						change: function(){
							me.cal_picked_qty();
						}
					},					
					// {
					// 	'label': 'Avalilable to Pick',
					// 	'fieldtype': 'Float',
					// 	'fieldname': 'to_pick_qty',
					// 	'read_only': 0,
					// 	'in_list_view': 1,
					// 	// change: function(){
					// 	// 	me.cal_picked_qty();
					// 	// }
					// },
					{
						'label': 'Avalilable Qty',
						'fieldtype': 'Float',
						'fieldname': 'available_qty',
						'read_only': 1,
						'in_list_view': 1,
						'columns': 2,
					},
					{
						'label': 'Actual Qty',
						'fieldtype': 'Float',
						'fieldname': 'actual_qty',
						'read_only': 1,
						'in_list_view': 1,
						'columns': 2,
					},
					{
						'label': 'Picked Qty',
						'fieldtype': 'Float',
						'fieldname': 'picked_qty',
						'read_only': 1,
						'in_list_view': 0,
					},
					
				],
				in_place_edit: false,
				data: this.data,
				get_data: function() {
					return this.data;
				},
			}
		];
	},
	cal_picked_qty: function(){
		var me = this;

		var selected_item_locations = me.get_selected_item_locations();
		var picked_qty = frappe.utils.sum((selected_item_locations || []).map(row => row.to_pick_qty));
		me.dialog.set_value('picked_qty', picked_qty);
		
	},
	set_item_location_data: function(){
		var me = this;
		me.item_locations_data = me.dialog.get_value('item_locations');
	},
	bind_events: function($wrapper) {
		var me = this;

		var $item_location_wrapper = me.get_item_location_wrapper();

		$item_location_wrapper.on('click', '.grid-row-check:checkbox', (e) => {
			me.cal_picked_qty();
		})

	},
	get_item_location_wrapper: function(){
		var me = this;
		return me.dialog.get_field('item_locations').$wrapper;
	},
	get_selected_item_locations: function() {
		var me = this;
		var selected_item_locations = [];
		var $item_location_wrapper = this.get_item_location_wrapper();
		var item_locations = me.dialog.get_value('item_locations');

		$.each($item_location_wrapper.find('.form-grid > .grid-body > .rows > .grid-row'), function (idx, row) {
			var pkg = $(row).find('.grid-row-check:checkbox');

			var item_location = item_locations[idx];
			
			if($(pkg).is(':checked')){
				selected_item_locations.push(item_location);
				item_location.__checked = 1;
			} else {
				item_location.__checked = 0;
			}
		});

		return selected_item_locations;
	},
	set_item_qty: function() {
		var me = this;
		var selected_item_locations = [];
		var $item_location_wrapper = this.get_item_location_wrapper();
		var item_locations = me.dialog.get_value('item_locations');
		var remaining_to_pick = me.dialog.get_value('remaining_to_pick');

		$.each($item_location_wrapper.find('.form-grid > .grid-body > .rows > .grid-row'), function (idx, row) {
			var pkg = $(row).find('.grid-row-check:checkbox');

			var item_location = item_locations[idx];
			
			if($(pkg).is(':checked')){
				selected_item_locations.push(item_location);
				item_location.__checked = 1;
			} else {
				item_location.__checked = 0;
				item_location.to_pick_qty = Math.min((remaining_to_pick || 0), (item_location.available_qty || 0))
			}
		});
		var item_locations2 = me.dialog.fields_dict.item_locations;
		item_locations2.grid.refresh();

		// return selected_item_locations;
	},
	set_item_locations_in_frm: function () {
		var me = this;
		var selected_item_locations = this.get_selected_item_locations();
		var item_code = me.values.item_code
		var sales_order = me.values.sales_order
		var sales_order_item = me.values.sales_order_item

		var loc = [];

		me.frm.doc.locations.forEach(function(value, idx){
			if (value.sales_order_item != sales_order_item){
				loc.push(value)
			}
		});
		me.frm.doc.locations = loc;
		
		(selected_item_locations || []).forEach(function(d){
			d.__checked = 0;
			var locations = me.frm.add_child('locations');
			frappe.model.set_value(locations.doctype, locations.name, 'item_code', d.item_code);
			frappe.model.set_value(locations.doctype, locations.name, 'customer', me.customer);
			frappe.model.set_value(locations.doctype, locations.name, 'so_picked_percent', me.so_picked_percent);
			frappe.model.set_value(locations.doctype, locations.name, 'so_qty', me.values.so_qty);
			frappe.model.set_value(locations.doctype, locations.name, 'delivery_date', me.delivery_date);
			frappe.model.set_value(locations.doctype, locations.name, 'date', me.date);
			frappe.model.set_value(locations.doctype, locations.name, 'qty', d.to_pick_qty);
			frappe.model.set_value(locations.doctype, locations.name, 'picked_qty', me.picked_qty || 0);
			frappe.model.set_value(locations.doctype, locations.name, 'available_qty', d.available_qty);
			frappe.model.set_value(locations.doctype, locations.name, 'actual_qty', d.actual_qty);
			frappe.model.set_value(locations.doctype, locations.name, 'sales_order', sales_order);
			frappe.model.set_value(locations.doctype, locations.name, 'sales_order_item', sales_order_item);
			frappe.model.set_value(locations.doctype, locations.name, 'batch_no', d.batch_no);
			frappe.model.set_value(locations.doctype, locations.name, 'order_item_priority', d.order_item_priority);
		})

		me.frm.doc.locations.forEach(function(d, idx){
			frappe.model.set_value(d.doctype, d.name, 'idx', idx + 1);
		});

		refresh_field('locations');
	},
});