"""Install the complete package or one independent provider at a time."""
from __future__ import annotations

from typing import Any
import probatio as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback

from .const import DOMAIN
from .providers.notices.provider import SOURCES,EVENT_PROVIDERS

PROVIDERS={'eds':'EDS · Strom',**{key:value['title'] for key,value in SOURCES.items()}}


class ArandjelovacLiveFlow(config_entries.ConfigFlow,domain=DOMAIN):
    VERSION=1

    async def _create_provider(self,provider: str) -> ConfigFlowResult:
        if provider not in PROVIDERS:return self.async_abort(reason='invalid_provider')
        await self.async_set_unique_id(f'{provider}:arandjelovac')
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=PROVIDERS[provider]+' · Aranđelovac',
                                       data={'provider':provider,'location':'arandjelovac'})

    async def async_step_user(self,user_input: dict[str,Any] | None=None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id='user',data_schema=vol.Schema({
                vol.Required('provider',default='all'):vol.In({'all':f'Komplettpaket · alle {len(PROVIDERS)} Quellen',**PROVIDERS})
            }))
        provider=user_input.get('provider','all')
        if provider!='all':return await self._create_provider(provider)
        configured={entry.unique_id for entry in self._async_current_entries()}
        missing=[key for key in PROVIDERS if f'{key}:arandjelovac' not in configured]
        if not missing:return self.async_abort(reason='already_configured')
        # Use ordinary HA import flows. Each source gets its own entry/coordinator.
        # Repeating "complete package" adds only missing sources after interruption.
        for key in missing[1:]:
            await self.hass.config_entries.flow.async_init(DOMAIN,context={'source':config_entries.SOURCE_IMPORT},data={'provider':key})
        return await self._create_provider(missing[0])

    async def async_step_import(self,user_input: dict[str,Any]) -> ConfigFlowResult:
        return await self._create_provider(user_input.get('provider',''))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ArandjelovacOptionsFlow()


class ArandjelovacOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self,user_input: dict[str,Any] | None=None) -> ConfigFlowResult:
        if user_input is not None:
            errors={}
            if not 1<=user_input.get('lookback_days',30)<=90:errors['lookback_days']='invalid_range'
            if not 1<=user_input.get('horizon_days',60)<=180:errors['horizon_days']='invalid_range'
            categories=user_input.get('categories','47')
            if not all(part.strip().isdigit() for part in str(categories).split(',')):errors['categories']='invalid_categories'
            if not errors:return self.async_create_entry(title='',data=user_input)
        else:errors={}
        options=self.config_entry.options;provider=self.config_entry.data['provider']
        fields={}
        if provider not in ('eds','putevi','manifestations'):fields[vol.Optional('lookback_days',default=options.get('lookback_days',30))]=vol.All(vol.Coerce(int),vol.Range(min=1,max=90))
        if provider in EVENT_PROVIDERS and provider!='manifestations':fields[vol.Optional('horizon_days',default=options.get('horizon_days',60))]=vol.All(vol.Coerce(int),vol.Range(min=1,max=180))
        if provider=='putevi':fields[vol.Optional('areas',default=options.get('areas','Aranđelovac, Darosava, Ranilović'))]=str
        if provider=='opstina':fields[vol.Optional('categories',default=options.get('categories','47'))]=str
        return self.async_show_form(step_id='init',data_schema=vol.Schema(fields),errors=errors)
