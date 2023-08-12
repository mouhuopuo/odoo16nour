from odoo import models, _, api


class HolidaysRequest(models.Model):
    _inherit = 'hr.leave'

    # def create(self, vals_list):
    #     holidays = super(HolidaysRequest, self).create(vals_list)
    #     print('hello bro', holidays)
    #     for holiday in holidays:
    #         print('holiday.holiday_allocation_id ', holiday.holiday_allocation_id)
    #         allocations = self.env['hr.leave.allocation'].search(
    #             [('holiday_status_id', '=', holiday.holiday_status_id.id)])
    #         print('all o ', allocations)
    #         for allocation in allocations:
    #             print('allocation : ', allocation)
    #             allocation._compute_from_holiday_status_id_with_emp(holiday.employee_id)
    #             # print('holiday : ', holiday.holiday_allocation_id)
    #     return holidays

    # @api.depends('number_of_days')
    # def check_if_grace_period_is_finished(self):
    #     for rec in self:

    # if rec.
    # I need to check the allocation for this leave if exceeded
    # the grace period and edit the duration after that
