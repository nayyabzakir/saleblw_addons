# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, _lt, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from odoo.tools.misc import formatLang
from collections import defaultdict, namedtuple
from dateutil.relativedelta import relativedelta


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        missing_fields = {'asset_id', 'amount', 'depreciation_beginning_date', 'date', 'asset_number_days'} - set(vals)
        if missing_fields:
            raise UserError(_('Some fields are missing %s', ', '.join(missing_fields)))
        asset = vals['asset_id']
        analytic_distribution = asset.analytic_distribution
        depreciation_date = vals.get('date', fields.Date.context_today(self))
        company_currency = asset.company_id.currency_id
        current_currency = asset.currency_id
        prec = company_currency.decimal_places
        amount_currency = vals['amount']
        amount = current_currency._convert(amount_currency, company_currency, asset.company_id, depreciation_date)
        # Keep the partner on the original invoice if there is only one
        partner = asset.original_move_line_ids.mapped('partner_id')
        partner = partner[:1] if len(partner) <= 1 else self.env['res.partner']
        ref_string = "Depreciation"
        if asset.is_prepaid == True:
            ref_string = "Prepayment"
            partner = asset.partner_id
        move_line_1 = {
            'name': asset.name,
            'partner_id': partner.id,
            'account_id': asset.account_depreciation_id.id,
            'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
            'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'analytic_distribution': analytic_distribution,
            'currency_id': current_currency.id,
            'amount_currency': -amount_currency,
        }
        move_line_2 = {
            'name': asset.name,
            'partner_id': partner.id,
            'account_id': asset.account_depreciation_expense_id.id,
            'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
            'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
            'analytic_distribution': analytic_distribution,
            'currency_id': current_currency.id,
            'amount_currency': amount_currency,
        }
        move_vals = {
            'partner_id': partner.id,
            'date': depreciation_date,
            'journal_id': asset.journal_id.id,
            'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
            'asset_id': asset.id,
            'ref': _("%s: %s",asset.name,ref_string),
            'asset_depreciation_beginning_date': vals['depreciation_beginning_date'],
            'asset_number_days': vals['asset_number_days'],
            'name': '/',
            'asset_value_change': vals.get('asset_value_change', False),
            'move_type': 'entry',
            'currency_id': current_currency.id,
        }
        return move_vals

    @api.depends('line_ids.asset_ids')
    def _compute_asset_ids(self):
        for record in self:
            record.asset_ids = record.line_ids.asset_ids
            record.count_asset = len(record.asset_ids)
            record.asset_id_display_name = _('Asset')
            record.draft_asset_exists = bool(record.asset_ids.filtered(lambda x: x.state == "draft"))

    def open_asset_view(self):
        return self.asset_id.open_asset(['form'])

    def action_open_asset_ids(self):
        return self.asset_ids.open_asset(['tree', 'form'])


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    asset_ids = fields.Many2many('account.asset', 'asset_move_line_rel', 'line_id', 'asset_id', string='Related Assets', copy=False)
    non_deductible_tax_value = fields.Monetary(compute='_compute_non_deductible_tax_value', currency_field='company_currency_id')

    def _get_computed_taxes(self):
        if self.move_id.asset_id:
            return self.tax_ids
        return super()._get_computed_taxes()

    def turn_as_asset(self):
        ctx = self.env.context.copy()
        ctx.update({
            'default_original_move_line_ids': [(6, False, self.env.context['active_ids'])],
            'default_company_id': self.company_id.id,
        })
        if any(line.move_id.state == 'draft' for line in self):
            raise UserError(_("All the lines should be posted"))
        if any(account != self[0].account_id for account in self.mapped('account_id')):
            raise UserError(_("All the lines should be from the same account"))
        return {
            "name": _("Turn as an asset"),
            "type": "ir.actions.act_window",
            "res_model": "account.asset",
            "views": [[False, "form"]],
            "target": "current",
            "context": ctx,
        }

    @api.depends('tax_ids.invoice_repartition_line_ids')
    def _compute_non_deductible_tax_value(self):
        """ Handle the specific case of non deductible taxes,
        such as "50% Non Déductible - Frais de voiture (Prix Excl.)" in Belgium.
        """
        non_deductible_tax_ids = self.tax_ids.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == 'tax' and not line.use_in_tax_closing
        ).tax_id

        res = {}
        if non_deductible_tax_ids:
            domain = [('move_id', 'in', self.move_id.ids)]
            tax_details_query, tax_details_params = self._get_query_tax_details_from_domain(domain)

            self.flush_model()
            self._cr.execute(f'''
                SELECT
                    tdq.base_line_id,
                    SUM(tdq.tax_amount_currency)
                FROM ({tax_details_query}) AS tdq
                JOIN account_move_line aml ON aml.id = tdq.tax_line_id
                JOIN account_tax_repartition_line trl ON trl.id = tdq.tax_repartition_line_id
                WHERE tdq.base_line_id IN %s
                AND trl.use_in_tax_closing IS FALSE
                GROUP BY tdq.base_line_id
            ''', tax_details_params + [tuple(self.ids)])

            res = {row['base_line_id']: row['sum'] for row in self._cr.dictfetchall()}

        for record in self:
            record.non_deductible_tax_value = res.get(record._origin.id, 0.0)
