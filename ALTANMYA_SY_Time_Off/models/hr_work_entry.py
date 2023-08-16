from collections import defaultdict
from contextlib import contextmanager
from dateutil.relativedelta import relativedelta
import itertools
from psycopg2 import OperationalError

from odoo import api, fields, models, tools, _

from odoo.exceptions import ValidationError


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    is_holiday_entry = fields.Boolean('Is holiday entry?', default=False)

    def write(self, vals):
        skip_check = not bool({'date_start', 'date_stop', 'employee_id', 'work_entry_type_id', 'active'} & vals.keys())
        if 'state' in vals:
            if vals['state'] == 'draft':
                vals['active'] = True
            elif vals['state'] == 'cancelled':
                vals['active'] = False
                skip_check &= all(self.mapped(lambda w: w.state != 'conflict'))

        if 'active' in vals:
            vals['state'] = 'draft' if vals['active'] else 'cancelled'

        with self._error_checking(skip=skip_check):
            return super(models.Model, self).write(vals)

    def action_validate(self):
        """
        Try to validate work entries.
        If some errors are found, set `state` to conflict for conflicting work entries
        and validation fails.
        :return: True if validation succeded
        """
        print('this should not get executed')
        holiday_entries = self.filtered(lambda work_entry: work_entry.is_holiday_entry == True)
        holiday_entries.write({'state': 'validated'})

        work_entries = self.filtered(lambda work_entry: work_entry.state != 'validated')
        if not work_entries._check_if_error():
            work_entries.write({'state': 'validated'})
            return True
        return False

    @api.model_create_multi
    def create(self, vals_list):
        work_entries = super().create(vals_list)
        print('entries before ', work_entries)
        for e in work_entries:
            print('state is : ', e.date_start, e.state)
        # work_entries_to_check = work_entries.filtered(lambda b: not b.is_holiday_entry)
        # print('entries to check ', work_entries_to_check)
        # work_entries_to_check._check_if_error()
        # print('entries after ', work_entries)
        for e in work_entries:
            if e.is_holiday_entry:
                e.state = 'draft'
        return work_entries

    @contextmanager
    def _error_checking(self, start=None, stop=None, skip=False, employee_ids=False):
        """
        Context manager used for conflicts checking.
        When exiting the context manager, conflicts are checked
        for all work entries within a date range. By default, the start and end dates are
        computed according to `self` (min and max respectively) but it can be overwritten by providing
        other values as parameter.
        :param start: datetime to overwrite the default behaviour
        :param stop: datetime to overwrite the default behaviour
        :param skip: If True, no error checking is done
        """
        try:
            print('ULTRA ', self.env.context.get('hr_work_entry_no_check', False))
            skip = skip or self.env.context.get('hr_work_entry_no_check', False)
            start = start or min(self.mapped('date_start'), default=False)
            stop = stop or max(self.mapped('date_stop'), default=False)
            if not skip and start and stop:
                work_entries = self.sudo().with_context(hr_work_entry_no_check=True).search([
                    ('date_start', '<', stop),
                    ('date_stop', '>', start),
                    ('state', 'not in', ('validated', 'cancelled')),
                    ('is_holiday_entry', '!=', True)
                ])
                print('reseting ', work_entries)
                work_entries._reset_conflicting_state()
            yield
        except OperationalError:
            # the cursor is dead, do not attempt to use it or we will shadow the root exception
            # with a "psycopg2.InternalError: current transaction is aborted, ..."
            skip = True
            raise
        finally:
            if not skip and start and stop:
                # New work entries are handled in the create method,
                # no need to reload work entries.
                work_entries.exists()._check_if_error()