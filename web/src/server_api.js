import {config} from './config';

async function api_method(path, options={}) {
    let url = new URL(config.api_path + path, config.api_url);

    if (options.params) {
        for (let key in options.params) {
            url.searchParams.set(key, options.params[key]);
        }
    }

    let request = fetch(url.toString(), {
        method: options.method,
        body: options.data,
        headers: {
            Origin: 'http://localhost:3000'
        }
    });
    let result = await request;
    if (options.json === undefined) options.json = true;

    if (options.json){
        return await result.json()
    } else {
        return result;
    }
}
export default {api_method};
