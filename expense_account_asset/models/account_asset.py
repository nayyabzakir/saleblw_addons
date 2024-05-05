# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta
from math import copysign

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero, formatLang, end_of

DAYS_PER_MONTH = 30
DAYS_PER_YEAR = DAYS_PER_MONTH * 12

class AccountAsset(models.Model):
    _inherit = 'account.asset'

    is_prepaid = fields.Boolean(default=False)
    partner_id = fields.Many2one('res.partner')

    @api.onchange('account_depreciation_id')
    def get_account_depreciation_id(self):
        for rec in self:
            if not rec.model_id:
                if rec.state == "model" and rec.is_prepaid == True and rec.account_depreciation_id:
                    rec.account_asset_id = rec.account_depreciation_id.id
                else:
                    rec.account_asset_id = False


    # @api.onchange('model_id')
    # def get_model_id(self):
    #     for rec in self:
    #         if rec.is_prepaid == True and rec.model_id:
    #             rec.account_asset_id = rec.model_id.account_asset_id.id
    #         else:
    #             rec.account_asset_id = False


    # def validate(self):
    #     # OVERRIDE
    #     res = super(AccountAsset, self).validate()
    #     for rec in self:
    #         if rec.depreciation_move_ids and rec.is_prepaid == True:
    #             for move in rec.depreciation_move_ids:
    #                 move.ref = _("%s: Prepayment", rec.name)
    #                 for line in move.line_ids:
    #                     line.partner_id = rec.partner_id.id
    #     return res

    def compute_depreciation_board(self):
        # OVERRIDE
        for rec in self:
            if rec.model_id:
                model = rec.model_id
                if model:
                    rec.method = model.method
                    rec.method_period = model.method_period
                    rec.method_progress_factor = model.method_progress_factor
                    rec.prorata_computation_type = model.prorata_computation_type
                    rec.analytic_distribution = model.analytic_distribution or rec.analytic_distribution
                    rec.account_asset_id = model.account_asset_id
                    rec.account_depreciation_id = model.account_depreciation_id
                    rec.account_depreciation_expense_id = model.account_depreciation_expense_id
                    rec.journal_id = model.journal_id
        return super(AccountAsset, self).compute_depreciation_board()