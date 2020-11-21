import {config, BITMAX, BINANCE} from './config';



async function api_method(path, options={}) {
    let url = new URL(config.api_path + path, config.api_url);
    // let password = getPassword();


    if (options.params) {
        for (let key in options.params) {
            url.searchParams.set(key, options.params[key]);
        }
    }

    // url.searchParams.set('password', password);

    switch (window.stock) {
        case BITMAX:
            url.searchParams.set('stock', 'bitmax');
            break;
        case BINANCE:
            url.searchParams.set('stock', 'binance');
            break;
    }

    let request = fetch(url.toString(), {
        method: options.method,
        body: options.data,
        headers: {
            Origin: 'https://localhost:3000'
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
