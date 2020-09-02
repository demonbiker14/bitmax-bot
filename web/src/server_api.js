import {config} from './config';

function getPassword() {
    let password = window.localStorage.password;
    if (!password) {
        password = window.prompt('Пароль:');
        window.localStorage.password = password;
    }
    return password;
}

async function api_method(path, options={}) {
    let url = new URL(config.api_path + path, config.api_url);
    let password = getPassword();

    if (options.params) {
        for (let key in options.params) {
            url.searchParams.set(key, options.params[key]);
        }
    }

    url.searchParams.set('password', password);

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
