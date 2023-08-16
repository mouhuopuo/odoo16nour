from odoo import api, fields, models


class Vacation(models.Model):
    _inherit = "hr.leave.type"

    is_configurable = fields.Boolean('Is Configurable? ', default=False)
    allowed_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('both', 'Both')
    ], string='Gender', default='both', required=True)
    marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('both', 'Both')
    ], string='Marital Status', default='both', required=True)
    is_repeated = fields.Boolean('repeated', default=False)
    balance_type = fields.Selection(
        [('new_balance', 'متكررة برصيد جديد كل مرة'), ('old_balance', 'متكررة بالرصيد السابق')],
        string='نوع رصيد الإجازة')
    number_of_allowed_days = fields.Integer('Number Of Allowed Days')
    number_of_required_work_days = fields.Integer('Number Of Required Work Days')
    is_connected_days = fields.Boolean('Connected Days', default=True)
    customized_to = fields.Selection([('none', 'None'),
                                      ('employee', 'Employee'),
                                      ('shift', 'Shift')],
                                     default='none')
    include_public_holidays = fields.Boolean('Include Public Holidays?', default=False)
    specified_employees = fields.Many2many('hr.employee')
    shift_ids = fields.Many2many('resource.calendar', string='Shifts')
    apply_pro_rata = fields.Boolean(string='Apply Pro Rata')
    is_sick_leave = fields.Boolean(string="إجازة مرضية")
    leave_date_from = fields.Integer(string='من اليوم', default=0)
    leave_date_to = fields.Integer(string='إلى اليوم', default=365)

    @api.onchange('customized_to')
    def empty_customization(self):
        if self.customized_to == 'none':
            self.specified_employees = [(6, 0, [])]
            self.shift_ids = [(6, 0, [])]
        elif self.customized_to == 'shift':
            self.specified_employees = [(6, 0, [])]
        elif self.customized_to == 'employee':
            self.shift_ids = [(6, 0, [])]

    # children = fields.Integer(string='Number Of Children', store=True)
