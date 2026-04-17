from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class WhatsAppTemplate(models.Model):
    _name = 'whatsapp.template'
    _description = 'WhatsApp Message Template'
    _order = 'name'

    TEMPLATE_STATUS = [
        ('approved', 'Approved'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('disabled', 'Disabled'),
        ('local', 'Local'),
    ]

    name = fields.Char(
        string='Template Name',
        required=True,
        unique=True
    )
    config_id = fields.Many2one(
        'whatsapp.config',
        string='WhatsApp Config',
        required=True
    )
    
    # Template Content
    body = fields.Text(
        string='Body Text',
        required=True,
        help='Template body text. Use {{1}}, {{2}}, etc. for parameters'
    )
    header = fields.Text(
        string='Header',
        help='Optional header text or media placeholder'
    )
    footer = fields.Char(
        string='Footer',
        help='Optional footer text'
    )
    
    # Parameters
    parameter_count = fields.Integer(
        string='Parameter Count',
        compute='_compute_parameter_count',
        store=True
    )
    parameters = fields.Text(
        string='Parameters',
        help='JSON list of parameter definitions'
    )

    # Buttons
    buttons = fields.Text(
        string='Buttons',
        help='JSON format button definitions'
    )

    # Status
    status = fields.Selection(
        TEMPLATE_STATUS,
        string='Status',
        default='local',
        readonly=True,
        help='Template approval status from Meta'
    )
    meta_template_id = fields.Char(
        string='Meta Template ID',
        readonly=True,
        help='Template ID from Meta API'
    )
    
    # Metadata
    description = fields.Text(
        string='Description',
        help='Template description for internal use'
    )
    category = fields.Char(
        string='Category',
        help='Template category (MARKETING, UTILITY, AUTHENTICATION)'
    )
    is_active = fields.Boolean(
        string='Active',
        default=True
    )
    last_sync = fields.Datetime(
        string='Last Sync',
        readonly=True
    )

    @api.depends('body')
    def _compute_parameter_count(self):
        import re
        for record in self:
            if record.body:
                params = re.findall(r'\{\{(\d+)\}\}', record.body)
                if params:
                    record.parameter_count = max(int(p) for p in params)
                else:
                    record.parameter_count = 0
            else:
                record.parameter_count = 0

    @api.constrains('name')
    def _validate_name(self):
        for record in self:
            if record.name and not record.name.replace('_', '').isalnum():
                raise ValidationError('Template name must be alphanumeric with underscores only.')

    def action_sync_from_meta(self):
        """Sync templates from Meta"""
        self.ensure_one()
        from .whatsapp_integration import WhatsAppAPI
        try:
            api = WhatsAppAPI(self.config_id)
            templates = api.get_templates()
            for template_data in templates:
                existing = self.search([
                    ('meta_template_id', '=', template_data.get('id'))
                ])
                if existing:
                    existing.write({
                        'status': template_data.get('status'),
                        'last_sync': fields.Datetime.now()
                    })
                else:
                    self.create({
                        'name': template_data.get('name'),
                        'body': template_data.get('body'),
                        'header': template_data.get('header'),
                        'footer': template_data.get('footer'),
                        'meta_template_id': template_data.get('id'),
                        'status': template_data.get('status'),
                        'config_id': self.config_id.id,
                        'last_sync': fields.Datetime.now()
                    })
            _logger.info(f'Synced {len(templates)} templates from Meta')
        except Exception as e:
            _logger.error(f'Error syncing templates: {str(e)}')
            raise ValidationError(f'Sync failed: {str(e)}')

    def get_parameter_list(self):
        """Parse and return parameter list"""
        if not self.parameters:
            return []
        try:
            return json.loads(self.parameters)
        except json.JSONDecodeError:
            return []

    def get_buttons(self):
        """Parse and return buttons"""
        if not self.buttons:
            return []
        try:
            return json.loads(self.buttons)
        except json.JSONDecodeError:
            return []
