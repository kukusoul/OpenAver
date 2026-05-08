import { stateConfig }       from '@/settings/state-config.js';
import { stateProviders }    from '@/settings/state-providers.js';
import { stateUI }           from '@/settings/state-ui.js';
import { stateClipSettings } from '@/settings/state-clip-settings.js';

function mergeState(...parts) {
    const target = {};
    for (const part of parts) {
        Object.defineProperties(target, Object.getOwnPropertyDescriptors(part));
    }
    return target;
}

document.addEventListener('alpine:init', () => {
    Alpine.data('settings', () => mergeState(
        stateConfig(),
        stateProviders(),
        stateUI(),
        stateClipSettings(),  // 必須最後，avoid init() last-wins 風險已由禁 init 解決
    ));
});
