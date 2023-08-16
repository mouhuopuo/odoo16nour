from odoo import fields, models

from odoo.tools import date_utils

from datetime import datetime


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    total_sick_leaves = fields.Integer(string='Total Sick Leaves', compute='compute_total_leaves', store=True)

    def compute_total_leaves(self, number_of_days=0):
        global total
        total_leaves = 0
        now = str(fields.Datetime.now())
        year = now[0:4]
        first_day_of_year = year + '-01-01'
        last_day_of_year = year + '-12-31'
        for rec in self:
            print('entered employee loop')
            total = self.env['hr.leave'].search(
                [('employee_ids', 'in', rec.id), ('holiday_status_id.is_sick_leave', '=', True),
                 ('state', 'not in', ['refuse']),
                 '|', ('request_date_from', '>=', first_day_of_year),
                 '&', ('request_date_from', '<', first_day_of_year), ('request_date_to', '>=', first_day_of_year),
                 ])
            print('total emp leaves')
            print(total)
        for rec in total:
            if str(rec.request_date_from) < first_day_of_year <= str(rec.request_date_to):
                date1 = datetime.strptime(str(rec.request_date_to), "%Y-%m-%d")
                date2 = datetime.strptime(first_day_of_year, "%Y-%m-%d")
                print('dates')
                print(date1)
                print(date2)
                diff = date1 - date2
                print(diff.days)
                # nod = rec.request_date_to - first_day_of_year
                total_leaves += diff.days
            else:
                total_leaves += rec.number_of_days
        print('number of days')
        print(number_of_days)
        total_leaves -= number_of_days
        print('total leaves')
        print(total_leaves)
        for rec in self:
            rec.total_sick_leaves = total_leaves