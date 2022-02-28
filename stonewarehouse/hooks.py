from . import __version__ as app_version

app_name = "stonewarehouse"
app_title = "Stonewarehouse"
app_publisher = "info@finbyz.com"
app_description = "Custom App"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@finbyz.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/stonewarehouse/css/stonewarehouse.css"
# app_include_js = "/assets/stonewarehouse/js/stonewarehouse.js"

# include js, css files in header of web template
# web_include_css = "/assets/stonewarehouse/css/stonewarehouse.css"
# web_include_js = "/assets/stonewarehouse/js/stonewarehouse.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "stonewarehouse/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "stonewarehouse.install.before_install"
# after_install = "stonewarehouse.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "stonewarehouse.uninstall.before_uninstall"
# after_uninstall = "stonewarehouse.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "stonewarehouse.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

doctype_js = {
	"Sales Order": "public/js/doctype_js/sales_order.js",
	"Pick List": "public/js/doctype_js/pick_list.js",
}

doctype_list_js = {
	"Pick List" : "public/js/doctype_js/pick_list_list.js",
}

override_doctype_dashboards = {
	"Sales Order": "stonewarehouse.stonewarehouse.dashboard.sales_order.get_data",
	"Pick List": "stonewarehouse.stonewarehouse.dashboard.pick_list.get_data",
}

doc_events = {
	"Sales Order": {
		"before_validate": [
			"stonewarehouse.stonewarehouse.doc_events.sales_order.before_validate"
		],
		"validate": [
			"stonewarehouse.stonewarehouse.doc_events.sales_order.validate"
		],
		"on_submit": "stonewarehouse.stonewarehouse.doc_events.sales_order.on_submit",
		"before_validate_after_submit": "stonewarehouse.stonewarehouse.doc_events.sales_order.before_validate_after_submit",
		"before_update_after_submit": "stonewarehouse.stonewarehouse.doc_events.sales_order.before_update_after_submit",
		"on_update_after_submit": "stonewarehouse.stonewarehouse.doc_events.sales_order.on_update_after_submit",
		"on_cancel": "stonewarehouse.stonewarehouse.doc_events.sales_order.on_cancel",
	},
	"Pick List": {
		"validate": "stonewarehouse.stonewarehouse.doc_events.pick_list.validate",
		"before_submit": "stonewarehouse.stonewarehouse.doc_events.pick_list.before_submit",
		"on_submit": "stonewarehouse.stonewarehouse.doc_events.pick_list.on_submit",
		"on_cancel": "stonewarehouse.stonewarehouse.doc_events.pick_list.on_cancel",
		"before_update_after_submit": "stonewarehouse.stonewarehouse.doc_events.pick_list.before_update_after_submit"
	},
	"Delivery Note": {
		"before_validate": [
			"stonewarehouse.stonewarehouse.doc_events.delivery_note.before_validate", 
		],
		"validate": [
			"stonewarehouse.stonewarehouse.doc_events.delivery_note.validate"
		],
		"before_submit": "stonewarehouse.stonewarehouse.doc_events.delivery_note.before_submit",
		"on_submit": "stonewarehouse.stonewarehouse.doc_events.delivery_note.on_submit",
		"on_cancel": "stonewarehouse.stonewarehouse.doc_events.delivery_note.on_cancel",
	}
}

scheduler_events = {
	"daily": [
		"stonewarehouse.stonewarehouse.doc_events.sales_order.schedule_daily",
	]
}

from stonewarehouse.override_default_class_method import set_item_locations
from erpnext.stock.doctype.pick_list.pick_list import PickList
PickList.set_item_locations = set_item_locations




# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"stonewarehouse.tasks.all"
# 	],
# 	"daily": [
# 		"stonewarehouse.tasks.daily"
# 	],
# 	"hourly": [
# 		"stonewarehouse.tasks.hourly"
# 	],
# 	"weekly": [
# 		"stonewarehouse.tasks.weekly"
# 	]
# 	"monthly": [
# 		"stonewarehouse.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "stonewarehouse.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "stonewarehouse.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "stonewarehouse.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"stonewarehouse.auth.validate"
# ]

