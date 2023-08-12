from collections import defaultdict

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models

from odoo.tools import get_timedelta


class AccrualPlanLevel(models.Model):
    _inherit = "hr.leave.accrual.level"
    _description = "Accrual Plan Level"

    # based_on_contract_or_allocation = fields.Selection([('allocation', 'Allocation'),
    #                                                     ('contract', 'Contract')],
    #                                                    default='allocation',
    #                                                    string="Is Based On Contract Or Allocation?")
    #
    # contract_start_count = fields.Integer(
    #     "Start after contract",
    #     default="1")
    # contract_start_type = fields.Selection(
    #     [('day', 'day(s)'),
    #      ('month', 'month(s)'),
    #      ('year', 'year(s)')],
    #     default='day', string=" ")

    action_with_unused_accruals = fields.Selection(
        [('postponed', 'Transferred to the next year'),
         ('contract_postponed', 'Transferred to the next contract year'),
         ('lost', 'Lost')],
        string="At the end of the calendar year, unused accruals will be",
        default='postponed', required='True')

    grace_period = fields.Integer("The period the employee is allowed to use the last year's unused accruals")
    grace_type = fields.Selection(
        [('day', 'day(s)'),
         ('month', 'month(s)')],
        default='day', string=" ")

    # @api.depends('start_count', 'start_type', 'contract_start_count', 'contract_start_type')
    # def _compute_sequence(self):
    #     # Not 100% accurate because of odd months/years, but good enough
    #     start_type_multipliers = {
    #         'day': 1,
    #         'month': 30,
    #         'year': 365,
    #     }
    #     for level in self:
    #         if level.based_on_contract_or_allocation == 'allocation':
    #             level.sequence = level.start_count * start_type_multipliers[level.start_type]
    #         elif level.based_on_contract_or_allocation == 'contract':
    #             level.sequence = level.contract_start_count * start_type_multipliers[level.contract_start_type]
    #
    # def _get_current_accrual_plan_level_id(self, date, level_ids=False):
    #     """
    #     Returns a pair (accrual_plan_level, idx) where accrual_plan_level is the level for the given date
    #      and idx is the index for the plan in the ordered set of levels
    #     """
    #     self.ensure_one()
    #     if not self.accrual_plan_id.level_ids:
    #         return (False, False)
    #     # Sort by sequence which should be equivalent to the level
    #     if not level_ids:
    #         level_ids = self.accrual_plan_id.level_ids.sorted('sequence')
    #     print('all levels : ', level_ids)
    #     current_level = False
    #     current_level_idx = -1
    #     for idx, level in enumerate(level_ids):
    #         start_count = level.start_count if level.based_on_contract_or_allocation == 'allocation' else level.contract_start_count
    #         start_type = level.start_type if level.based_on_contract_or_allocation == 'allocation' else level.contract_start_type
    #         print(level, 'date ', date, self.date_from + get_timedelta(start_count, start_type),
    #               get_timedelta(start_count, start_type))
    #         if date > self.date_from + get_timedelta(start_count, start_type):
    #             print('level is : ', level)
    #             current_level = level
    #             current_level_idx = idx
    #     # If transition_mode is set to `immediately` or we are currently on the first level
    #     # the current_level is simply the first level in the list.
    #     if current_level_idx <= 0 or self.accrual_plan_id.transition_mode == "immediately":
    #         return (current_level, current_level_idx)
    #     # In this case we have to verify that the 'previous level' is not the current one due to `end_of_accrual`
    #     start_count2 = current_level.start_count if current_level.based_on_contract_or_allocation == 'allocation' else current_level.contract_start_count
    #     start_type2 = current_level.start_type if current_level.based_on_contract_or_allocation == 'allocation' else current_level.contract_start_type
    #     level_start_date = self.date_from + get_timedelta(start_count2, start_type2)
    #     previous_level = level_ids[current_level_idx - 1]
    #     # If the next date from the current level's start date is before the last call of the previous level
    #     # return the previous level
    #     if current_level._get_next_date(level_start_date) < previous_level._get_next_date(level_start_date):
    #         return (previous_level, current_level_idx - 1)
    #     return (current_level, current_level_idx)
    #
    # def _process_accrual_plans(self, date_to=False, force_period=False):
    #     """
    #     This method is part of the cron's process.
    #     The goal of this method is to retroactively apply accrual plan levels and progress from nextcall to date_to or today.
    #     If force_period is set, the accrual will run until date_to in a prorated way (used for end of year accrual actions).
    #     """
    #     date_to = date_to or fields.Date.today()
    #     first_allocation = _(
    #         """This allocation have already ran once, any modification won't be effective to the days allocated to the employee. If you need to change the configuration of the allocation, cancel and create a new one.""")
    #     for allocation in self:
    #         level_ids = allocation.accrual_plan_id.level_ids.sorted('sequence')
    #         if not level_ids:
    #             continue
    #         if not allocation.nextcall:
    #             first_level = level_ids[0]
    #             start_count = first_level.start_count if first_level.based_on_contract_or_allocation == 'allocation' else first_level.contract_start_count
    #             start_type = first_level.start_type if first_level.based_on_contract_or_allocation == 'allocation' else first_level.contract_start_type
    #             first_level_start_date = allocation.date_from + get_timedelta(start_count, start_type)
    #             if date_to < first_level_start_date:
    #                 # Accrual plan is not configured properly or has not started
    #                 continue
    #             allocation.lastcall = max(allocation.lastcall, first_level_start_date)
    #             allocation.nextcall = first_level._get_next_date(allocation.lastcall)
    #             if len(level_ids) > 1:
    #                 start_count = level_ids[1].start_count if level_ids[
    #                                                               1].based_on_contract_or_allocation == 'allocation' else \
    #                     level_ids[1].contract_start_count
    #                 start_type = level_ids[1].start_type if level_ids[
    #                                                             1].based_on_contract_or_allocation == 'allocation' else \
    #                     level_ids[1].contract_start_type
    #                 second_level_start_date = allocation.date_from + get_timedelta(start_count,
    #                                                                                start_type)
    #                 allocation.nextcall = min(second_level_start_date, allocation.nextcall)
    #             allocation._message_log(body=first_allocation)
    #         days_added_per_level = defaultdict(lambda: 0)
    #         while allocation.nextcall <= date_to:
    #             (current_level, current_level_idx) = allocation._get_current_accrual_plan_level_id(allocation.nextcall)
    #             nextcall = current_level._get_next_date(allocation.nextcall)
    #             # Since _get_previous_date returns the given date if it corresponds to a call date
    #             # this will always return lastcall except possibly on the first call
    #             # this is used to prorate the first number of days given to the employee
    #             period_start = current_level._get_previous_date(allocation.lastcall)
    #             period_end = current_level._get_next_date(allocation.lastcall)
    #             # Also prorate this accrual in the event that we are passing from one level to another
    #             if current_level_idx < (
    #                     len(level_ids) - 1) and allocation.accrual_plan_id.transition_mode == 'immediately':
    #                 next_level = level_ids[current_level_idx + 1]
    #                 start_count = next_level.start_count if next_level.based_on_contract_or_allocation == 'allocation' else next_level.contract_start_count
    #                 start_type = next_level.start_type if next_level.based_on_contract_or_allocation == 'allocation' else next_level.contract_start_type
    #
    #                 current_level_last_date = allocation.date_from + get_timedelta(start_count,
    #                                                                                start_type)
    #                 if allocation.nextcall != current_level_last_date:
    #                     nextcall = min(nextcall, current_level_last_date)
    #             # We have to check for end of year actions if it is within our period
    #             #  since we can create retroactive allocations.
    #             if allocation.lastcall.year < allocation.nextcall.year and \
    #                     current_level.action_with_unused_accruals == 'postponed' and \
    #                     current_level.postpone_max_days > 0:
    #                 # Compute number of days kept
    #                 allocation_days = allocation.number_of_days - allocation.leaves_taken
    #                 allowed_to_keep = max(0, current_level.postpone_max_days - allocation_days)
    #                 number_of_days = min(allocation_days, current_level.postpone_max_days)
    #                 allocation.number_of_days = number_of_days + allocation.leaves_taken
    #                 total_gained_days = sum(days_added_per_level.values())
    #                 days_added_per_level.clear()
    #                 days_added_per_level[current_level] = min(total_gained_days, allowed_to_keep)
    #             gained_days = allocation._process_accrual_plan_level(
    #                 current_level, period_start, allocation.lastcall, period_end, allocation.nextcall)
    #             days_added_per_level[current_level] += gained_days
    #             if current_level.maximum_leave > 0 and sum(days_added_per_level.values()) > current_level.maximum_leave:
    #                 days_added_per_level[current_level] -= sum(
    #                     days_added_per_level.values()) - current_level.maximum_leave
    #
    #             allocation.lastcall = allocation.nextcall
    #             allocation.nextcall = nextcall
    #             if force_period and allocation.nextcall > date_to:
    #                 allocation.nextcall = date_to
    #                 force_period = False
    #
    #         if days_added_per_level:
    #             number_of_days_to_add = allocation.number_of_days + sum(days_added_per_level.values())
    #             # Let's assume the limit of the last level is the correct one
    #             allocation.number_of_days = min(number_of_days_to_add,
    #                                             current_level.maximum_leave + allocation.leaves_taken) if current_level.maximum_leave > 0 else number_of_days_to_add
