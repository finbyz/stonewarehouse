erpnext.selling.SalesOrderController = erpnext.selling.SalesOrderController.extend({
	// onload: function(doc, dt, dn) {
	// 	this._super();
	// },
	refresh: function (doc, dt, dn) {
		var me = this;
		// FinByz Changes Start
		// this._super();
		// FinByz Changes Over
		let allow_delivery = false;

		if (doc.docstatus == 1) {
			if (this.frm.doc.per_delivered == 0) {
				this.frm.add_custom_button(__('Unpick All'), () => this.unpick_all(this.frm.doc))
			}

			if (this.frm.has_perm("submit")) {
				if (doc.status === 'On Hold') {
					// un-hold
					this.frm.add_custom_button(__('Resume'), function () {
						me.frm.cscript.update_status('Resume', 'Draft')
					}, __("Status"));

					if (flt(doc.per_delivered, 6) < 100 || flt(doc.per_billed) < 100) {
						// close
						this.frm.add_custom_button(__('Close'), () => this.close_sales_order(), __("Status"))
					}
				}
				else if (doc.status === 'Closed') {
					// un-close
					this.frm.add_custom_button(__('Re-open'), function () {
						me.frm.cscript.update_status('Re-open', 'Draft')
					}, __("Status"));
				}
			}
			if (doc.status !== 'Closed') {
				if (doc.status !== 'On Hold') {
					allow_delivery = this.frm.doc.items.some(item => item.delivered_by_supplier === 0 && item.qty > flt(item.delivered_qty))
						&& !this.frm.doc.skip_delivery_note

					if (this.frm.has_perm("submit")) {
						if (flt(doc.per_delivered, 6) < 100 || flt(doc.per_billed) < 100) {
							// hold
							this.frm.add_custom_button(__('Hold'), () => this.hold_sales_order(), __("Status"))
							// close
							this.frm.add_custom_button(__('Close'), () => this.close_sales_order(), __("Status"))
						}
					}
					if (this.frm.doc.per_picked !== 100) {
						this.frm.add_custom_button(__('Pick List'), () => this.create_pick_list(), __('Create'));
					}

					// delivery note
					if (flt(doc.per_delivered, 6) < 100 && ["Sales", "Shopping Cart"].indexOf(doc.order_type) !== -1 && allow_delivery) {
						this.frm.add_custom_button(__('Delivery Note'), () => this.make_delivery_note_based_on_delivery_date(), __('Create'));
						this.frm.add_custom_button(__('Work Order'), () => this.make_work_order(), __('Create'));
					}

					// FinByz Changes Start
					// sales invoice
					// if(flt(doc.per_billed, 6) < 100) {
					// 	this.frm.add_custom_button(__('Invoice'), () => me.make_sales_invoice(), __('Create'));
					// }
					// FinByz Changes End

					// material request
					if (!doc.order_type || ["Sales", "Shopping Cart"].indexOf(doc.order_type) !== -1
						&& flt(doc.per_delivered, 6) < 100) {
						this.frm.add_custom_button(__('Material Request'), () => this.make_material_request(), __('Create'));
						this.frm.add_custom_button(__('Request for Raw Materials'), () => this.make_raw_material_request(), __('Create'));
					}

					// make purchase order
					// FinByz Changes Start
					// this.frm.add_custom_button(__('Purchase Order'), () => this.make_purchase_order(), __('Create'));
					// FinByz Changes End

					// maintenance
					// FinByz Changes Start
					// if(flt(doc.per_delivered, 2) < 100 &&
					// 		["Sales", "Shopping Cart"].indexOf(doc.order_type)===-1) {
					// 	this.frm.add_custom_button(__('Maintenance Visit'), () => this.make_maintenance_visit(), __('Create'));
					// 	this.frm.add_custom_button(__('Maintenance Schedule'), () => this.make_maintenance_schedule(), __('Create'));
					// }
					// FinByz Changes End

					// project
					// FinByz Changes Start
					// if(flt(doc.per_delivered, 2) < 100 && ["Sales", "Shopping Cart"].indexOf(doc.order_type)!==-1 && allow_delivery) {
					// 		this.frm.add_custom_button(__('Project'), () => this.make_project(), __('Create'));
					// }
					// FinByz Changes End

					if (!doc.auto_repeat) {
						this.frm.add_custom_button(__('Subscription'), function () {
							erpnext.utils.make_subscription(doc.doctype, doc.name)
						}, __('Create'))
					}

					if (doc.docstatus === 1 && !doc.inter_company_order_reference) {
						let me = this;
						frappe.model.with_doc("Customer", me.frm.doc.customer, () => {
							let customer = frappe.model.get_doc("Customer", me.frm.doc.customer);
							let internal = customer.is_internal_customer;
							let disabled = customer.disabled;
							if (internal === 1 && disabled === 0) {
								me.frm.add_custom_button("Inter Company Order", function () {
									me.make_inter_company_order();
								}, __('Create'));
							}
						});
					}
				}
				// payment request
				// FinByz Changes Start
				// if(flt(doc.per_billed)<100) {
				// 	this.frm.add_custom_button(__('Payment Request'), () => this.make_payment_request(), __('Create'));
				// 	this.frm.add_custom_button(__('Payment'), () => this.make_payment_entry(), __('Create'));
				// }
				// FinByz Changes End
				this.frm.page.set_inner_btn_group_as_primary(__('Create'));
			}
		}

		if (this.frm.doc.docstatus === 0) {
			this.frm.add_custom_button(__('Quotation'),
				function () {
					erpnext.utils.map_current_doc({
						method: "erpnext.selling.doctype.quotation.quotation.make_sales_order",
						source_doctype: "Quotation",
						target: me.frm,
						setters: [
							{
								label: "Customer",
								fieldname: "party_name",
								fieldtype: "Link",
								options: "Customer",
								default: me.frm.doc.customer || undefined
							}
						],
						get_query_filters: {
							company: me.frm.doc.company,
							docstatus: 1,
							status: ["!=", "Lost"]
						}
					})
				}, __("Get items from"));
		}

		this.order_type(doc);
	},

	unpick_all: function (doc, dt, dn) {
		frappe.call({
			method: "stonewarehouse.stonewarehouse.doc_events.pick_list.unpick_item",
			args: {
				'sales_order': doc.name
			},
			callback: function (r) {
				frappe.msgprint(r.message);
			}
		})
	},



	close_sales_order: function () {
		this.frm.cscript.update_status("Close", "Closed")
		frappe.call({
			method: "stonewarehouse.stonewarehouse.doc_events.pick_list.unpick_item",
			args: {
				'sales_order': this.frm.doc.name,
			},
			callback: function (r) {
				frappe.msgprint(r.message);
			}
		})
	},
	// Finbyz Changes Start
	create_pick_list() {
		frappe.model.open_mapped_doc({
			method: "stonewarehouse.stonewarehouse.doc_events.sales_order.make_pick_list",
			frm: this.frm
		})
	},
	make_delivery_note_based_on_delivery_date: function() {
		var me = this;

		var delivery_dates = [];
		$.each(this.frm.doc.items || [], function(i, d) {
			if(!delivery_dates.includes(d.delivery_date)) {
				delivery_dates.push(d.delivery_date);
			}
		});

		var item_grid = this.frm.fields_dict["items"].grid;
		if(!item_grid.get_selected().length && delivery_dates.length > 1) {
			var dialog = new frappe.ui.Dialog({
				title: __("Select Items based on Delivery Date"),
				fields: [{fieldtype: "HTML", fieldname: "dates_html"}]
			});

			var html = $(`
				<div style="border: 1px solid #d1d8dd">
					<div class="list-item list-item--head">
						<div class="list-item__content list-item__content--flex-2">
							${__('Delivery Date')}
						</div>
					</div>
					${delivery_dates.map(date => `
						<div class="list-item">
							<div class="list-item__content list-item__content--flex-2">
								<label>
								<input type="checkbox" data-date="${date}" checked="checked"/>
								${frappe.datetime.str_to_user(date)}
								</label>
							</div>
						</div>
					`).join("")}
				</div>
			`);

			var wrapper = dialog.fields_dict.dates_html.$wrapper;
			wrapper.html(html);

			dialog.set_primary_action(__("Select"), function() {
				var dates = wrapper.find('input[type=checkbox]:checked')
					.map((i, el) => $(el).attr('data-date')).toArray();

				if(!dates) return;

				$.each(dates, function(i, d) {
					$.each(item_grid.grid_rows || [], function(j, row) {
						if(row.doc.delivery_date == d) {
							row.doc.__checked = 1;
						}
					});
				})
				me.make_delivery_note();
				dialog.hide();
			});
			dialog.show();
		} else {
			this.make_delivery_note();
		}
	},

	make_delivery_note: function() {
		frappe.model.open_mapped_doc({
			method: "stonewarehouse.stonewarehouse.doc_events.sales_order.make_delivery_note",
			frm: me.frm
		})
	},
	// Finbyz Changes End
})
$.extend(cur_frm.cscript, new erpnext.selling.SalesOrderController({ frm: cur_frm }));

frappe.ui.form.on('Sales Order', {
	lotwise_balance: function(frm){
		window.open(window.location.href.split('app')[0] + "app/query-report/Batch-Wise Balance" + "/?" + "company="+ frm.doc.company + "&" + "sales_order=" + frm.doc.name,"_blank")
	},

	before_save: function (frm) {
		frm.trigger('calculate_total');
	},

	company: function (frm) {
		frm.trigger('order_priority');
	},

	calculate_total: function (frm) {
		let total_qty = 0.0
		let total_picked_qty = 0.0
		let total_picked_weight = 0.0
		let total_net_weight = 0.0

		frm.doc.items.forEach(function (d) {
			total_qty += flt(d.qty);
			total_picked_qty += flt(d.picked_qty);
			d.picked_weight = flt(d.weight_per_unit * d.picked_qty)
			total_picked_weight += flt(d.picked_weight);
			d.total_weight = flt(d.weight_per_unit * d.qty)
			total_net_weight = flt(d.weight_per_unit * d.qty)
		});

		frm.set_value("total_qty", total_qty);
		frm.set_value("total_picked_qty", total_picked_qty);
		frm.set_value("total_picked_weight", total_picked_weight);
	},
	transaction_date: function(frm){
		frm.trigger('order_priority')
	},
	order_priority: function(frm){
		if (frm.doc.order_priority && frm.doc.company && frm.doc.transaction_date){
			frappe.call({
				method: "stonewarehouse.stonewarehouse.doc_events.sales_order.update_order_rank_",
				args: {
					'date': frm.doc.transaction_date,
					'order_priority': frm.doc.order_priority,
					'company': frm.doc.company
				},
				callback: function (r) {
					if (r.message){
						frm.set_value('order_item_priority', r.message.order_item_priority)
						frm.set_value('order_rank', r.message.order_rank)
					}
				}
			})
		}
	},
	correct_picked_qty: function (frm) {
			frappe.call({
				method: "stonewarehouse.stonewarehouse.doc_events.pick_list.correct_picked_qty",
				args: {
					'sales_order': frm.doc.name
				},
				callback: function (r) {
					frappe.msgprint(r.message);
				}
		});
	},
})
frappe.ui.form.on("Sales Order Item", {
	qty: (frm, cdt, cdn) => {
		let d = locals[cdt][cdn];
		frm.events.calculate_total(frm)
	},

	unpick_item: function (frm, cdt, cdn) {
		let d = locals[cdt][cdn]
		
		frappe.call({
			method: "stonewarehouse.stonewarehouse.doc_events.pick_list.unpick_picked_qty_sales_order",
			args: {
				'sales_order': frm.doc.name,
				'sales_order_item': d.name,
				'item_code':d.item_code
			},
			callback: function (r) {
				frappe.msgprint(r.message);
			}
		})
	},
})