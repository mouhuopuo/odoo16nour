# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2005-2006 Axelor SARL. (http://www.axelor.com)

from collections import defaultdict
import logging
from datetime import datetime, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.resource.models.resource import HOURS_PER_DAY
from odoo.addons.hr_holidays.models.hr_leave import get_employee_from_context
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _
from odoo.tools.float_utils import float_round
from odoo.tools.date_utils import get_timedelta
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class HR_alloction_scheduledEmpolyee(models.Model):
    _inherit = 'hr.employee'

    time_of_type_em = fields.Many2one('hr.leave.type',  string='time_of_type')
    accrual_plan_em = fields.Many2one('hr.leave.accrual.plan',
                                      domain="['|', ('time_off_type_id', '=', False), ('time_off_type_id', '=', time_of_type_em)]",
                                      string='accrual_plan')

    @api.onchange('time_of_type_em')
    def _onchange_time_of_type_em(self):
        if self.time_of_type_em:
            self.accrual_plan_em = False
            self.accrual_plan_em = self.env['hr.leave.accrual.plan'].search(
                ['|', ('time_off_type_id', '=', False), ('time_off_type_id', '=', self.time_of_type_em.id)], limit=1)


class HR_alloction_scheduled(models.Model):
    _inherit = 'hr.leave.allocation'

    def test_scheduled_from_hr(self):
        employees = self.env['hr.employee'].search([])
        new = ''
        arr = []
        for employee in employees:
            mm = self.env['hr.leave.allocation'].search([('employee_id', '=', employee.id)])
            if mm:
                print('test_schedule mm -=>>>', mm)
                print('done form scheduled............======>')
            else:
                print('test_schedule employee.id -=>>>', employee.id)
                arr.append(employee)
        print('arr -=>>>', arr)

        for rec in arr:
            print(rec.first_contract_date)
            print(rec.time_of_type_em)
            print('test after confirm')
            if rec.employee_type == 'employee' or rec.employee_type == 'student' or rec.employee_type == 'trainee':
                if rec.time_of_type_em and rec.accrual_plan_em and rec.first_contract_date:
                    new = self.env['hr.leave.allocation'].create({
                        'private_name': 'created from schedule action',
                        'allocation_type': 'accrual',
                        'holiday_status_id': rec.time_of_type_em.id,
                        'accrual_plan_id': rec.accrual_plan_em.id,
                        'number_of_days': 0,
                        'employee_id': rec.id,
                        'employee_ids': [(6, 0, [rec.id])],
                        'state': 'draft',
                        'date_from': rec.first_contract_date,
                    })
                    new.action_confirm()

            print('new..', new)
