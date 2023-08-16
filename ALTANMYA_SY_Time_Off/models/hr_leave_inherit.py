from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from pytz import timezone, utc
import pytz

from datetime import datetime
from odoo.exceptions import UserError


class HRLeave(models.Model):
    _inherit = 'hr.leave'

    employee_total_leaves = fields.Integer(string='إجمالي الإجازات المرضية من بداية السنة',
                                           compute='_compute_employee_leaves', store=True)

    @api.onchange('employee_ids')
    def onchange_employee_id(self):
        domain = ['|', ('requires_allocation', '=', 'no'),
                  ('has_valid_allocation', '=', True),
                  '|', ('allowed_gender', '=', 'both'), ('allowed_gender', '=', self.employee_id.gender),
                  '|', ('marital_status', '=', 'both'), ('marital_status', '=', self.employee_id.marital)
                  ]
        print(domain)
        if self.employee_id:
            print('gender', self.employee_ids[0].gender)
            print('marital', self.employee_ids[0].marital)
        # self.compute_employee_service_days()
        print('prorata', self.calculate_days_based_on_pro_rata())
        return {'domain': {'holiday_status_id': domain}}

    def compute_employee_service_days(self, leave_start_date):
        if self.employee_ids or self.employee_id:
            employee_contract_date = self.env['hr.employee'].search(
                [('id', '=', self.employee_ids[0]._origin.id)]).first_contract_date
            if employee_contract_date:
                employee_service_days = leave_start_date.date() - employee_contract_date
                print('employee_service_days', employee_service_days.days)
                if employee_service_days.days >= 0:
                    print('in if', employee_service_days.days)
                    return employee_service_days.days
                else:
                    print('in else', employee_service_days.days)
                    return 0

    def compute_total_leaves_custom_type(self, leave_type):
        global total
        total_leaves = 0
        now = str(fields.Datetime.now())
        year = now[0:4]
        for rec in self:
            total = self.env['hr.leave'].search(
                [('employee_ids', 'in', rec.employee_ids[0]),
                 ('state', 'not in', ['refuse']),
                 ('holiday_status_id.name', '=', leave_type)])
        for rec in total:
            total_leaves += rec.number_of_days

    def compute_non_repeated_leaves_total(self):
        for rec in self:
            # print('employee name in repeated', rec.employee_ids[0].id)
            non_repeated_leaves = self.env['hr.leave'].search(
                [('holiday_status_id.is_repeated', '=', False), ('employee_id', '=', rec.employee_ids[0].id),
                 ('holiday_status_id.is_sick_leave', '=', False), ('holiday_status_id', '=', rec.holiday_status_id.id)])
            print('non_repeated_leaves', non_repeated_leaves)
            if len(non_repeated_leaves) > 1:
                return len(non_repeated_leaves)
        return 0

    def compute_total_employee_leaves(self, holiday_type):
        employee_leaves = self.env['hr.leave'].search(
            [('employee_id', '=', self.employee_ids[0].id), ('holiday_status_id', '=', holiday_type.id)])
        total_leave_days = 0
        for leave in employee_leaves:
            total_leave_days += leave.number_of_days
        print('total leaves', total_leave_days)
        return total_leave_days

    def _compute_number_of_days(self):
        super(HRLeave, self)._compute_number_of_days()
        # I need to iterate over self
        for holiday in self:
            if holiday.holiday_status_id.is_configurable:
                if holiday.holiday_status_id.is_connected_days:
                    if holiday.holiday_status_id.include_public_holidays:
                        unusaldays = holiday.employee_id._get_unusual_days(holiday.date_from, holiday.date_to)
                        print('unusaldays', unusaldays)
                        if unusaldays:
                            print('first ', holiday.number_of_days)
                            holiday.number_of_days = holiday.number_of_days + len(
                                [elem for elem in unusaldays.values() if elem])
                            holiday.number_of_days = int(holiday.number_of_days)
                    else:
                        unusaldays = holiday.employee_id._get_unusual_days(holiday.date_from, holiday.date_to)
                        print('unusaldays', unusaldays)
                        unusal_dates = []
                        usual_dates = []
                        public_holidays = self.env['resource.calendar.leaves'].search(
                            ['&', ('resource_id', '=', False),
                             ('calendar_id', 'in', (holiday.employee_id.resource_calendar_id.id, False))])
                        for key, value in unusaldays.items():
                            print('d ', key, value)
                            if value:
                                unusal_dates.append(key)
                            else:
                                usual_dates.append(key)
                        print('dates: ', unusal_dates, '------', usual_dates)
                        temp_dates = []
                        for date in unusal_dates:
                            is_usal = False
                            for public_holiday in public_holidays:
                                print('public holiday is : ', public_holiday)
                                print('start and end are ',
                                      public_holiday.date_from.astimezone(timezone("Asia/baghdad")),
                                      public_holiday.date_to)
                                print('start & end ',
                                      public_holiday.date_from.astimezone(timezone("Asia/baghdad")).strftime(
                                          "%Y-%m-%d"), 'to ',
                                      public_holiday.date_to.astimezone(timezone("Asia/baghdad")).strftime("%Y-%m-%d"))
                                if public_holiday.date_from.astimezone(timezone("Asia/baghdad")).strftime(
                                        "%Y-%m-%d") <= date <= public_holiday.date_to.astimezone(
                                    timezone("Asia/baghdad")).strftime("%Y-%m-%d"):
                                    is_usal = True
                            if not is_usal:
                                temp_dates.append(date)
                        for rec in temp_dates:
                            usual_dates.append(rec)
                        print('final dates ', usual_dates)
                        if unusaldays:
                            print('holiday.number_of_days ', holiday.number_of_days)
                            holiday.number_of_days = len(
                                [elem for elem in usual_dates])
                            print('holiday.number_of_days ', holiday.number_of_days)
                            holiday.number_of_days = int(holiday.number_of_days)

    @api.constrains('holiday_status_id')
    def check_leave_if_specified_to_employee(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.customized_to == 'employee':
                test = self.env['hr.leave.type'].search(
                    [('id', '=', self.holiday_status_id.id), ('specified_employees', 'in', self.employee_ids[0].id)])
                print('test', test)
                if not test:
                    raise ValidationError('هذه الإجازة غير مخصصة لك')

    @api.constrains('holiday_status_id')
    def check_leave_if_specified_to_shift(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.customized_to == 'shift':
                test = self.env['hr.leave.type'].search(
                    [('id', '=', self.holiday_status_id.id),
                     ('shift_ids', 'in', self.employee_ids[0].resource_calendar_id.id)])
                print('test', test)
                if not test:
                    raise ValidationError('هذه الإجازة غير مخصصة لك')

    @api.constrains('holiday_status_id')
    def check_repeated_leaves(self):
        if self.holiday_status_id.is_configurable:
            print('compute_non_repeated_leaves_total()', self.compute_non_repeated_leaves_total())
            print('balance type', self.holiday_status_id.balance_type)
            # print('employee : ', self.employee_ids[0].name)
            if self.compute_non_repeated_leaves_total() >= 1 and self.holiday_status_id.balance_type != 'new_balance':
                raise ValidationError('هذا الموظف قد قام بالفعل بأخذ إجازة من هذا النوع و هو لا يحق له أكثر من مرة')
            return True

    @api.constrains('holiday_status_id')
    def check_if_exceeded_allowed_days(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.is_repeated and self.holiday_status_id.balance_type == 'new_balance':
                if self.number_of_days > self.calculate_days_based_on_pro_rata():
                    raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')
            elif self.holiday_status_id.is_repeated and self.holiday_status_id.balance_type == 'old_balance':
                if self.compute_total_employee_leaves(self.holiday_status_id) > self.calculate_days_based_on_pro_rata():
                    raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')
            else:
                if self.number_of_days > self.calculate_days_based_on_pro_rata():
                    raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')

    # @api.constrains('holiday_status_id')
    # def check_if_exceeded_allowed_days_prorata(self):
    #     if self.holiday_status_id.is_configurable:
    #         print('hiiiiiii', self.compute_total_employee_leaves(self.holiday_status_id))
    #         if self.compute_total_employee_leaves(
    #                 self.holiday_status_id) > self.calculate_days_based_on_pro_rata() and not self.check_repeated_leaves():
    #             raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')

    @api.constrains('holiday_status_id')
    def check_if_required_days_are_met(self):
        if self.holiday_status_id.is_configurable:
            required_work_days = self.holiday_status_id.number_of_required_work_days
            print('required work days')
            print(required_work_days)
            print(self.compute_employee_service_days(self.date_from))
            if required_work_days > self.compute_employee_service_days(self.date_from):
                print('lol 1', required_work_days)
                print('lol 2', self.compute_employee_service_days(self.date_from))
                raise ValidationError('هذا النوع من الإجازات لا يحق لهذا الموظف بعد')
            else:
                pass

    def calculate_normal_days(self):
        return self.holiday_status_id.number_of_allowed_days

    # for pro rata leaves
    def calculate_days_based_on_pro_rata(self):
        if self.employee_ids or self.employee_id:
            if self.holiday_status_id.apply_pro_rata:
                employee_contract_date = self.env['hr.employee'].search(
                    [('id', '=', self.employee_ids[0]._origin.id)]).first_contract_date
                now = str(self.date_from)
                year = now[0:4]
                current_month = now[5:7]
                contract_year = str(employee_contract_date)[0:4]
                print('current year', year, 'contract year', contract_year)
                contract_month = str(employee_contract_date)[5:7]
                print('contract in last year', str(int(contract_year) + 1), str(employee_contract_date))
                print('month ', contract_month, current_month)
                if year == contract_year:
                    diff = 12 - int(contract_month)
                    # if diff != 12:
                    print('diff', diff)
                    # if diff < 11:
                    allowed_days_for_this_employee = self.holiday_status_id.number_of_allowed_days - (
                            self.holiday_status_id.number_of_allowed_days * (
                            diff / 12))
                    print('allowed days', round(allowed_days_for_this_employee))
                    return round(allowed_days_for_this_employee)
                else:
                    return self.holiday_status_id.number_of_allowed_days
            else:
                return self.holiday_status_id.number_of_allowed_days
        else:
            return self.holiday_status_id.number_of_allowed_days

    # sick leaves
    # @api.model_create_multi
    # def create(self, vals_list):
    #     holidays = super(HRLeave, self.with_context(mail_create_nosubscribe=True)).create(vals_list)
    #     print('vals list')
    #     print(vals_list)
    #     self.env['hr.employee'].search([('id', '=', vals_list[0]['employee_ids'][0][0])]).compute_total_leaves()
    #     return holidays

    def write(self, values):
        result = super(HRLeave, self).write(values)
        # self.env['hr.employee'].search([('id', '=', self.employee_ids[0].id)]).compute_total_leaves()
        # if self.holiday_status_id.is_configurable:
        #     self.check_leave_if_specified_to_employee()
        #     self.check_employees_number_configurable_leave()
        #     # self.check_repeated_leaves()
        #     self.check_leave_if_specified_to_shift()
        #     self.check_employees_total_leaves()
        #     self.check_if_exceeded_allowed_days()
        #     self.check_if_required_days_are_met()
        #     self.check_matching_gender()
        #     self.check_matching_marital_status()
        return result

    @api.onchange('holiday_status_id', 'employee_ids')
    def _compute_employee_leaves(self):
        for rec in self:
            if len(rec.employee_ids) >= 1:
                rec.employee_total_leaves = rec.employee_ids[0]._origin.total_sick_leaves
                print('emp total')
                print(rec.employee_ids[0]._origin.total_sick_leaves)
                print(rec.employee_total_leaves)

    # def read(self, fields=None, load='_classic_read'):
    #     res = super(HRLeave, self).read(fields=fields, load=load)
    #     for rec in self:
    #         rec._compute_employee_leaves()
    #         self.env['hr.employee'].search([('id', '=', rec.employee_ids[0].id)]).compute_total_leaves()
    #     return res

    @api.constrains('holiday_status_id')
    def check_employees_number_configurable_leave(self):
        if self.holiday_status_id.is_configurable and len(self.employee_ids) > 1:
            raise ValidationError('لا يمكن أن يتم اختيار أكثر من موظف عند تقديم هذا النوع من الإجازات')

    @api.constrains('holiday_status_id')
    def check_employees_total_leaves(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.is_sick_leave:
                print('constraint entered')
                print(self.holiday_status_id.leave_date_to, self.employee_total_leaves)
                print(self.employee_total_leaves + self.number_of_days)
                print(self.holiday_status_id.leave_date_from)
                print('-------debug--------')
                print(self.holiday_status_id.leave_date_to >=
                      self.employee_total_leaves + self.number_of_days >= self.holiday_status_id.leave_date_from)
                print(self.holiday_status_id.leave_date_to != 0)
                print(self.holiday_status_id.leave_date_from, self.employee_total_leaves)
                print(self.holiday_status_id.leave_date_from <= self.employee_total_leaves)
                if not (
                        self.holiday_status_id.leave_date_to >=
                        self.employee_total_leaves + self.number_of_days >= self.holiday_status_id.leave_date_from \
                        and self.holiday_status_id.leave_date_to != 0 \
                        and self.holiday_status_id.leave_date_from <= self.employee_total_leaves + self.number_of_days):
                    raise ValidationError('لا يحق للموظف أخذ هذا النوع من الإجازة المرضية')

    @api.constrains('holiday_status_id')
    def check_matching_gender(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.allowed_gender != self.employee_ids[
                0].gender and self.holiday_status_id.allowed_gender != 'both':
                raise ValidationError('هذا النوع من الإجازات لا يحق لهذا الموظف')

    @api.constrains('holiday_status_id')
    def check_matching_marital_status(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.marital_status != self.employee_ids[
                0].marital and self.holiday_status_id.marital_status != 'both':
                raise ValidationError('هذا النوع من الإجازات لا يحق لهذا الموظف')

    def action_approve(self):
        # if validation_type == 'both': this method is the first approval approval
        # if validation_type != 'both': this method calls action_validate() below
        if any(holiday.state != 'confirm' for holiday in self):
            raise UserError(_('Time off request must be confirmed ("To Approve") in order to approve it.'))

        current_employee = self.env.user.employee_id
        self.filtered(lambda hol: hol.validation_type == 'both').write(
            {'state': 'validate1', 'first_approver_id': current_employee.id})

        # Post a second message, more verbose than the tracking message
        for holiday in self.filtered(lambda holiday: holiday.employee_id.user_id):
            user_tz = timezone(holiday.tz)
            utc_tz = pytz.utc.localize(holiday.date_from).astimezone(user_tz)
            holiday.message_post(
                body=_(
                    'Your %(leave_type)s planned on %(date)s has been accepted',
                    leave_type=holiday.holiday_status_id.display_name,
                    date=utc_tz.replace(tzinfo=None)
                ),
                partner_ids=holiday.employee_id.user_id.partner_id.ids)

        self.filtered(lambda hol: not hol.validation_type == 'both').action_validate()
        if not self.env.context.get('leave_fast_create'):
            self.activity_update()

        return True

    def action_validate(self):
        res = super().action_validate()
        matched = self.env['hr.work.entry'].search([('leave_id', '=', self.id)])
        print('id : ', self.id, self._origin.id)
        print('matched before for ', matched)
        if self.id and matched:
            print('matched work entries', matched)
            unusaldays = self.employee_id._get_unusual_days(self.date_from, self.date_to)
            print('unusual areee', unusaldays)
            dates = []
            if unusaldays:
                for key, value in unusaldays.items():
                    if value:
                        dates.append(key)
                print('dates : ', dates)
            work_entry = self.env['hr.work.entry']
            for rec in matched:
                print('vals : ', rec.name, rec.contract_id, rec.employee_id, rec.work_entry_type_id, rec.date_start,
                      rec.date_stop)
                work_entry = rec
            name = work_entry.name
            # contract_id = work_entry.contract_id
            employee_id = work_entry.employee_id
            work_entry_type_id = work_entry.work_entry_type_id

            print('id : ', self.id)
            print(type(work_entry.date_start))
            for d in dates:
                print('d type ', type(d))
                start = datetime.strptime(d, '%Y-%m-%d')
                end = datetime.strptime(d, '%Y-%m-%d')
                start_time = datetime(
                    year=start.year,
                    month=start.month,
                    day=start.day,
                    hour=5,
                    minute=0,
                )
                end_time = datetime(
                    year=end.year,
                    month=end.month,
                    day=end.day,
                    hour=14,
                    minute=0,
                )
                end_time_mod = datetime(
                    year=end.year,
                    month=end.month,
                    day=end.day,
                    hour=21,
                    minute=0,
                )
                print('start and end : ', start_time, end_time)
                if self.holiday_status_id.is_connected_days:
                    conflict_with_public_holiday = self.env['hr.work.entry'].search(
                        [('date_start', '>=', start_time), ('date_stop', '<=', end_time_mod),
                         ('work_entry_type_id.code', '=', 'HOLIDAY'),
                         ('employee_id', '=', work_entry.employee_id.id),
                         ('state', '=', 'draft')])
                    # conflict_with_holiday = self.env['hr.work.entry'].search(
                    #     [('date_start', '>=', start_time), ('date_stop', '<=', end_time_mod),
                    #      ('employee_id', '=', work_entry.employee_id.id),
                    #      ('state', '=', 'draft')])
                    # for conflict in conflict_with_holiday:
                    #     conflict.unlink()
                    print('conflict public holiday ', conflict_with_public_holiday)
                    if not conflict_with_public_holiday:
                        print('conflict_with_public_holiday ', conflict_with_public_holiday)
                        new = self.env['hr.work.entry'].create({
                            'name': name,
                            'employee_id': employee_id.id,
                            'contract_id': employee_id.contract_id.id,
                            'work_entry_type_id': work_entry_type_id.id,
                            'date_start': start_time,
                            'date_stop': end_time,
                            'leave_id': self.id,
                            'is_holiday_entry': True,
                            'duration': 9,
                        })
                        new.write({
                            'state': 'draft'
                        })
        elif self.id:
            unusaldays = self.employee_id._get_unusual_days(self.date_from, self.date_to)
            print('unusual areee 2', unusaldays)
            dates = []
            if unusaldays:
                for key, value in unusaldays.items():
                    if value:
                        dates.append(key)
                print('dates : ', dates)
            work_entry = self.env['hr.work.entry']
            # for rec in matched:
            #     print('vals : ', rec.name, rec.contract_id, rec.employee_id, rec.work_entry_type_id, rec.date_start,
            #           rec.date_stop)
            #     work_entry = rec
            name = self.holiday_status_id.work_entry_type_id.name
            # contract_id = work_entry.contract_id
            employee_id = self.employee_id.name
            work_entry_type_id = self.holiday_status_id.work_entry_type_id.id

            print('id : ', self.id)
            # print(type(work_entry.date_start))
            for d in dates:
                print('d type ', type(d))
                start = datetime.strptime(d, '%Y-%m-%d')
                end = datetime.strptime(d, '%Y-%m-%d')
                start_time = datetime(
                    year=start.year,
                    month=start.month,
                    day=start.day,
                    hour=5,
                    minute=0,
                )
                end_time = datetime(
                    year=end.year,
                    month=end.month,
                    day=end.day,
                    hour=14,
                    minute=0,
                )
                end_time_mod = datetime(
                    year=end.year,
                    month=end.month,
                    day=end.day,
                    hour=21,
                    minute=0,
                )
                print('start and end : ', start_time, end_time)
                if self.holiday_status_id.is_connected_days:
                    conflict_with_public_holiday = self.env['hr.work.entry'].search(
                        [('date_start', '>=', start_time), ('date_stop', '<=', end_time_mod),
                         ('work_entry_type_id.code', '=', 'HOLIDAY'),
                         ('employee_id', '=', self.employee_id.id),
                         ('state', '=', 'draft')])
                    print('conflict public holiday ', conflict_with_public_holiday)
                    if not conflict_with_public_holiday:
                        print('conflict_with_public_holiday ', conflict_with_public_holiday)
                        new = self.env['hr.work.entry'].create({
                            'name': name,
                            'employee_id': self.employee_id.id,
                            'contract_id': self.employee_id.contract_id.id,
                            'work_entry_type_id': work_entry_type_id,
                            'date_start': start_time,
                            'date_stop': end_time,
                            'leave_id': self.id,
                            'is_holiday_entry': True,
                            'duration': 9,
                        })
                        new.write({
                            'state': 'draft'
                        })

        return res

    def _cancel_work_entry_conflict(self):
        """
        Creates a leave work entry for each hr.leave in self.
        Check overlapping work entries with self.
        Work entries completely included in a leave are archived.
        e.g.:
            |----- work entry ----|---- work entry ----|
                |------------------- hr.leave ---------------|
                                    ||
                                    vv
            |----* work entry ****|
                |************ work entry leave --------------|
        """
        if not self:
            return

        # 1. Create a work entry for each leave
        work_entries_vals_list = []
        for leave in self:
            contracts = leave.employee_id.sudo()._get_contracts(leave.date_from, leave.date_to,
                                                                states=['open', 'close'])
            for contract in contracts:
                # Generate only if it has aleady been generated
                if leave.date_to >= contract.date_generated_from and leave.date_from <= contract.date_generated_to:
                    work_entries_vals_list += contracts._get_work_entries_values(leave.date_from, leave.date_to)
        print('work_entries_vals_list ', work_entries_vals_list)
        new_leave_work_entries = self.env['hr.work.entry'].create(work_entries_vals_list)

        if new_leave_work_entries:
            # 2. Fetch overlapping work entries, grouped by employees
            start = min(self.mapped('date_from'), default=False)
            stop = max(self.mapped('date_to'), default=False)
            work_entry_groups = self.env['hr.work.entry']._read_group([
                ('date_start', '<', stop),
                ('date_stop', '>', start),
                ('employee_id', 'in', self.employee_id.ids),
            ], ['work_entry_ids:array_agg(id)', 'employee_id'], ['employee_id', 'date_start', 'date_stop'], lazy=False)
            work_entries_by_employee = defaultdict(lambda: self.env['hr.work.entry'])
            for group in work_entry_groups:
                employee_id = group.get('employee_id')[0]
                work_entries_by_employee[employee_id] |= self.env['hr.work.entry'].browse(group.get('work_entry_ids'))

            # 3. Archive work entries included in leaves
            included = self.env['hr.work.entry']
            overlappping = self.env['hr.work.entry']
            for work_entries in work_entries_by_employee.values():
                # Work entries for this employee
                new_employee_work_entries = work_entries & new_leave_work_entries
                previous_employee_work_entries = work_entries - new_leave_work_entries

                # Build intervals from work entries
                leave_intervals = new_employee_work_entries._to_intervals()
                conflicts_intervals = previous_employee_work_entries._to_intervals()

                # Compute intervals completely outside any leave
                # Intervals are outside, but associated records are overlapping.
                outside_intervals = conflicts_intervals - leave_intervals

                overlappping |= self.env['hr.work.entry']._from_intervals(outside_intervals)
                included |= previous_employee_work_entries - overlappping
            overlappping.write({'leave_id': False})
            included.write({'active': False})
