import itertools
import pytz
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.addons.resource.models.resource import datetime_to_string, string_to_datetime, Intervals

from datetime import datetime, timedelta


class HrContract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    def _get_contract_work_entries_values(self, date_start, date_stop):
        start_dt = pytz.utc.localize(date_start) if not date_start.tzinfo else date_start
        end_dt = pytz.utc.localize(date_stop) if not date_stop.tzinfo else date_stop

        contract_vals = []
        bypassing_work_entry_type_codes = self._get_bypassing_work_entry_type_codes()

        attendances_by_resource = self._get_attendance_intervals(start_dt, end_dt)

        resource_calendar_leaves = self.env['resource.calendar.leaves'].search(self._get_leave_domain(start_dt, end_dt))
        print('resource calendar leaves', resource_calendar_leaves)
        # {resource: resource_calendar_leaves}
        leaves_by_resource = defaultdict(lambda: self.env['resource.calendar.leaves'])
        for leave in resource_calendar_leaves:
            leaves_by_resource[leave.resource_id.id] |= leave

        print('leaves_by_resource : ', leaves_by_resource)
        tz_dates = {}
        for contract in self:
            employee = contract.employee_id
            calendar = contract.resource_calendar_id
            resource = employee.resource_id
            tz = pytz.timezone(calendar.tz)
            print('emp calendar is : ', calendar)

            attendances = attendances_by_resource[resource.id]

            # Other calendars: In case the employee has declared time off in another calendar
            # Example: Take a time off, then a credit time.
            # YTI TODO: This mimics the behavior of _leave_intervals_batch, while waiting to be cleaned
            # in master.
            resources_list = [self.env['resource.resource'], resource]
            result = defaultdict(lambda: [])
            for leave in itertools.chain(leaves_by_resource[False], leaves_by_resource[resource.id]):
                for resource in resources_list:
                    # Global time off is not for this calendar, can happen with multiple calendars in self
                    if resource and leave.calendar_id and leave.calendar_id != calendar and not leave.resource_id:
                        continue
                    tz = tz if tz else pytz.timezone((resource or contract).tz)
                    if (tz, start_dt) in tz_dates:
                        start = tz_dates[(tz, start_dt)]
                    else:
                        start = start_dt.astimezone(tz)
                        tz_dates[(tz, start_dt)] = start
                    if (tz, end_dt) in tz_dates:
                        end = tz_dates[(tz, end_dt)]
                    else:
                        end = end_dt.astimezone(tz)
                        tz_dates[(tz, end_dt)] = end
                    dt0 = string_to_datetime(leave.date_from).astimezone(tz)
                    dt1 = string_to_datetime(leave.date_to).astimezone(tz)
                    result[resource.id].append((max(start, dt0), min(end, dt1), leave))
            mapped_leaves = {r.id: Intervals(result[r.id]) for r in resources_list}
            leaves = mapped_leaves[resource.id]

            print('period leaves : ', leaves)
            real_attendances = attendances - leaves
            if contract.has_static_work_entries() or not leaves:
                # Empty leaves means empty real_leaves
                real_leaves = attendances - real_attendances
                print('attendances : ', attendances)
                print('real_attendances in if ', real_attendances)
                print('real_leaves in if ', real_leaves)
            else:
                # In the case of attendance based contracts use regular attendances to generate leave intervals
                static_attendances = calendar._attendance_intervals_batch(
                    start_dt, end_dt, resources=resource, tz=tz)[resource.id]
                real_leaves = static_attendances & leaves

            if not contract.has_static_work_entries():
                # An attendance based contract might have an invalid planning, by definition it may not happen with
                # static work entries.
                # Creating overlapping slots for example might lead to a single work entry.
                # In that case we still create both work entries to indicate a problem (conflicting W E).
                split_attendances = []
                for attendance in real_attendances:
                    if attendance[2] and len(attendance[2]) > 1:
                        split_attendances += [(attendance[0], attendance[1], a) for a in attendance[2]]
                    else:
                        split_attendances += [attendance]
                real_attendances = split_attendances
            print('real attendances : ', real_attendances)
            for intrval in real_attendances:
                print('intervaaal ', intrval)
            for i in attendances:
                print('i : ', i)
            for j in real_leaves:
                print('j : ', j)

            # A leave period can be linked to several resource.calendar.leave
            split_leaves = []
            for leave_interval in leaves:
                if leave_interval[2] and len(leave_interval[2]) > 1:
                    split_leaves += [(leave_interval[0], leave_interval[1], l) for l in leave_interval[2]]
                else:
                    split_leaves += [(leave_interval[0], leave_interval[1], leave_interval[2])]
            leaves = split_leaves

            # Attendances
            default_work_entry_type = contract._get_default_work_entry_type()
            for interval in real_attendances:
                work_entry_type = 'work_entry_type_id' in interval[2] and interval[2].work_entry_type_id[:1] \
                                  or default_work_entry_type
                # All benefits generated here are using datetimes converted from the employee's timezone
                contract_vals += [dict([
                                           ('name', "%s: %s" % (work_entry_type.name, employee.name)),
                                           ('date_start', interval[0].astimezone(pytz.utc).replace(tzinfo=None)),
                                           ('date_stop', interval[1].astimezone(pytz.utc).replace(tzinfo=None)),
                                           ('work_entry_type_id', work_entry_type.id),
                                           ('employee_id', employee.id),
                                           ('contract_id', contract.id),
                                           ('company_id', contract.company_id.id),
                                           ('state', 'draft'),
                                       ] + contract._get_more_vals_attendance_interval(interval))]

            print('real leaves ', real_leaves)
            entry_type = ""
            type_id = None
            for interval in real_leaves:
                print('interval of real leave ', interval)
                # Could happen when a leave is configured on the interface on a day for which the
                # employee is not supposed to work, i.e. no attendance_ids on the calendar.
                # In that case, do try to generate an empty work entry, as this would raise a
                # sql constraint error
                if interval[0] == interval[1]:  # if start == stop
                    continue
                leave_entry_type = contract._get_interval_leave_work_entry_type(interval, leaves,
                                                                                bypassing_work_entry_type_codes)
                interval_start = interval[0].astimezone(pytz.utc).replace(tzinfo=None)
                interval_stop = interval[1].astimezone(pytz.utc).replace(tzinfo=None)
                contract_vals += [dict([
                                           ('name', "%s%s" % (
                                               leave_entry_type.name + ": " if leave_entry_type else "",
                                               employee.name)),
                                           ('date_start', interval_start),
                                           ('date_stop', interval_stop),
                                           ('work_entry_type_id', leave_entry_type.id),
                                           ('employee_id', employee.id),
                                           ('company_id', contract.company_id.id),
                                           ('state', 'draft'),
                                           ('contract_id', contract.id),
                                       ] + contract._get_more_vals_leave_interval(interval, leaves))]
                entry_type = leave_entry_type.name
                type_id = leave_entry_type.id
            print('dates ', date_start, date_stop)
            holidays_in_this_period = self.env['resource.calendar.leaves'].search(
                [('date_from', '>=', date_start - timedelta(hours=3)), ('date_to', '<=', date_stop - timedelta(hours=3))
                    , ('resource_id', '=', False)])
            print('holidays_in_this_period', holidays_in_this_period)
            for rec in holidays_in_this_period:
                delta = rec.date_to + timedelta(hours=3) - rec.date_from + timedelta(hours=3)
                days = []
                already_filled = []
                not_found = []
                if delta != 0:
                    for i in range(delta.days + 1):
                        day = rec.date_from + timedelta(hours=3, days=i)
                        print(day)
                        days.append(day)
                    for d in days:
                        i = 0
                        for val in contract_vals:
                            print('value is : ', val)
                            if d.strftime('%Y-%m-%d') == val['date_start'].strftime('%Y-%m-%d') and val[
                                'employee_id'] == employee.id:
                                already_filled.append(d)
                                i += 1
                        if i == 0:
                            not_found.append(d)
                            # print('val : ', val)
                    print('already ', already_filled)
                    print('not_found ', not_found)
                for da in not_found:
                    print('da : ', da)
                    start = da.replace(hour=5, minute=00)
                    end = da.replace(hour=14, minute=00)
                    contract_vals += [dict([
                        ('name', f'{rec.work_entry_type_id.name}: {employee.name}'),
                        ('date_start', start),
                        ('date_stop', end),
                        ('duration', 9),
                        ('is_holiday_entry', True),
                        ('work_entry_type_id', rec.work_entry_type_id.id),
                        ('employee_id', employee.id),
                        ('company_id', contract.company_id.id),
                        ('state', 'draft'),
                        ('contract_id', contract.id),
                    ])]
        return contract_vals

    # def _get_more_vals_attendance_interval(self, interval):

    #
    #     return [
    #                 ('name', 'Generic Time Off'),
    #                 ('date_start', datetime(2023, 6, 24, 6, 0)),
    #                 ('date_stop', datetime(2023, 6, 24, 11, 0)),
    #                 ('work_entry_type_id', 2),
    #                 ('employee_id', 3),
    #                 ('company_id', 1),
    #                 ('state', 'draft'),
    #                 ('contract_id', 4),
    #             ]
    #
    # def _get_work_entries_values(self, date_start, date_stop):
    #     """
    #     Generate a work_entries list between date_start and date_stop for one contract.
    #     :return: list of dictionnary.
    #     """
    #     contract_vals = self._get_contract_work_entries_values(date_start, date_stop)
    #
    #     # {contract_id: ([dates_start], [dates_stop])}
    #     mapped_contract_dates = defaultdict(lambda: ([], []))
    #     for x in contract_vals:
    #         mapped_contract_dates[x['contract_id']][0].append(x['date_start'])
    #         mapped_contract_dates[x['contract_id']][1].append(x['date_stop'])
    #
    #     for contract in self:
    #         # If we generate work_entries which exceeds date_start or date_stop, we change boundaries on contract
    #         if contract_vals:
    #             #Handle empty work entries for certain contracts, could happen on an attendance based contract
    #             #NOTE: this does not handle date_stop or date_start not being present in vals
    #             dates_stop = mapped_contract_dates[contract.id][1]
    #             if dates_stop:
    #                 date_stop_max = max(dates_stop)
    #                 if date_stop_max > contract.date_generated_to:
    #                     contract.date_generated_to = date_stop_max
    #
    #             dates_start = mapped_contract_dates[contract.id][0]
    #             if dates_start:
    #                 date_start_min = min(dates_start)
    #                 if date_start_min < contract.date_generated_from:
    #                     contract.date_generated_from = date_start_min
    #
    #     return contract_vals
    #
    # def _get_contract_work_entries_values(self, date_start, date_stop):
    #     start_dt = pytz.utc.localize(date_start) if not date_start.tzinfo else date_start
    #     end_dt = pytz.utc.localize(date_stop) if not date_stop.tzinfo else date_stop
    #
    #     contract_vals = []
    #     bypassing_work_entry_type_codes = self._get_bypassing_work_entry_type_codes()
    #
    #     attendances_by_resource = self._get_attendance_intervals(start_dt, end_dt)
    #
    #     resource_calendar_leaves = self.env['resource.calendar.leaves'].search(self._get_leave_domain(start_dt, end_dt))
    #     # {resource: resource_calendar_leaves}
    #     leaves_by_resource = defaultdict(lambda: self.env['resource.calendar.leaves'])
    #     for leave in resource_calendar_leaves:
    #         leaves_by_resource[leave.resource_id.id] |= leave
    #
    #     print('hello', date_start, date_stop)
    #
    #     tz_dates = {}
    #     for contract in self:
    #         employee = contract.employee_id
    #         calendar = contract.resource_calendar_id
    #         resource = employee.resource_id
    #         tz = pytz.timezone(calendar.tz)
    #
    #         attendances = attendances_by_resource[resource.id]
    #
    #         # Other calendars: In case the employee has declared time off in another calendar
    #         # Example: Take a time off, then a credit time.
    #         # YTI TODO: This mimics the behavior of _leave_intervals_batch, while waiting to be cleaned
    #         # in master.
    #         resources_list = [self.env['resource.resource'], resource]
    #         result = defaultdict(lambda: [])
    #         for leave in itertools.chain(leaves_by_resource[False], leaves_by_resource[resource.id]):
    #             for resource in resources_list:
    #                 # Global time off is not for this calendar, can happen with multiple calendars in self
    #                 if resource and leave.calendar_id and leave.calendar_id != calendar and not leave.resource_id:
    #                     continue
    #                 tz = tz if tz else pytz.timezone((resource or contract).tz)
    #                 if (tz, start_dt) in tz_dates:
    #                     start = tz_dates[(tz, start_dt)]
    #                 else:
    #                     start = start_dt.astimezone(tz)
    #                     tz_dates[(tz, start_dt)] = start
    #                 if (tz, end_dt) in tz_dates:
    #                     end = tz_dates[(tz, end_dt)]
    #                 else:
    #                     end = end_dt.astimezone(tz)
    #                     tz_dates[(tz, end_dt)] = end
    #                 dt0 = string_to_datetime(leave.date_from).astimezone(tz)
    #                 dt1 = string_to_datetime(leave.date_to).astimezone(tz)
    #                 result[resource.id].append((max(start, dt0), min(end, dt1), leave))
    #         mapped_leaves = {r.id: Intervals(result[r.id]) for r in resources_list}
    #         leaves = mapped_leaves[resource.id]
    #
    #         real_attendances = attendances - leaves
    #         if contract.has_static_work_entries() or not leaves:
    #             # Empty leaves means empty real_leaves
    #             real_leaves = attendances - real_attendances
    #         else:
    #             # In the case of attendance based contracts use regular attendances to generate leave intervals
    #             static_attendances = calendar._attendance_intervals_batch(
    #                 start_dt, end_dt, resources=resource, tz=tz)[resource.id]
    #             real_leaves = static_attendances & leaves
    #
    #         if not contract.has_static_work_entries():
    #             # An attendance based contract might have an invalid planning, by definition it may not happen with
    #             # static work entries.
    #             # Creating overlapping slots for example might lead to a single work entry.
    #             # In that case we still create both work entries to indicate a problem (conflicting W E).
    #             split_attendances = []
    #             for attendance in real_attendances:
    #                 if attendance[2] and len(attendance[2]) > 1:
    #                     split_attendances += [(attendance[0], attendance[1], a) for a in attendance[2]]
    #                 else:
    #                     split_attendances += [attendance]
    #             real_attendances = split_attendances
    #
    #         # A leave period can be linked to several resource.calendar.leave
    #         split_leaves = []
    #         for leave_interval in leaves:
    #             if leave_interval[2] and len(leave_interval[2]) > 1:
    #                 split_leaves += [(leave_interval[0], leave_interval[1], l) for l in leave_interval[2]]
    #             else:
    #                 split_leaves += [(leave_interval[0], leave_interval[1], leave_interval[2])]
    #         leaves = split_leaves
    #
    #         # Attendances
    #         default_work_entry_type = contract._get_default_work_entry_type()
    #         for interval in real_attendances:
    #             work_entry_type = 'work_entry_type_id' in interval[2] and interval[2].work_entry_type_id[:1]\
    #                 or default_work_entry_type
    #             # All benefits generated here are using datetimes converted from the employee's timezone
    #             contract_vals += [dict([
    #                 ('name', "%s: %s" % (work_entry_type.name, employee.name)),
    #                 ('date_start', interval[0].astimezone(pytz.utc).replace(tzinfo=None)),
    #                 ('date_stop', interval[1].astimezone(pytz.utc).replace(tzinfo=None)),
    #                 ('work_entry_type_id', work_entry_type.id),
    #                 ('employee_id', employee.id),
    #                 ('contract_id', contract.id),
    #                 ('company_id', contract.company_id.id),
    #                 ('state', 'draft'),
    #             ] + contract._get_more_vals_attendance_interval(interval))]
    #
    #         for interval in real_leaves:
    #             # Could happen when a leave is configured on the interface on a day for which the
    #             # employee is not supposed to work, i.e. no attendance_ids on the calendar.
    #             # In that case, do try to generate an empty work entry, as this would raise a
    #             # sql constraint error
    #             if interval[0] == interval[1]:  # if start == stop
    #                 continue
    #             leave_entry_type = contract._get_interval_leave_work_entry_type(interval, leaves, bypassing_work_entry_type_codes)
    #             interval_start = interval[0].astimezone(pytz.utc).replace(tzinfo=None)
    #             interval_stop = interval[1].astimezone(pytz.utc).replace(tzinfo=None)
    #             contract_vals += [dict([
    #                 ('name', "%s%s" % (leave_entry_type.name + ": " if leave_entry_type else "", employee.name)),
    #                 ('date_start', interval_start),
    #                 ('date_stop', interval_stop),
    #                 ('work_entry_type_id', leave_entry_type.id),
    #                 ('employee_id', employee.id),
    #                 ('company_id', contract.company_id.id),
    #                 ('state', 'draft'),
    #                 ('contract_id', contract.id),
    #             ] + contract._get_more_vals_leave_interval(interval, leaves))]
    #     return contract_vals
