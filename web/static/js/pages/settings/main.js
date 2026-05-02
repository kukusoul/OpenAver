import { stateConfig }    from '@/settings/state-config.js';
import { stateProviders } from '@/settings/state-providers.js';
import { stateUI }        from '@/settings/state-ui.js';

document.addEventListener('alpine:init', () => {
    Alpine.data('settings', () => ({
        ...stateConfig(),
        ...stateProviders(),
        ...stateUI(),
    }));
});
