import { createStore } from 'redux';
import {updated_symbols, update_symbol, reducer} from './redux_utils';

const store = createStore(reducer,
    {
        symbols: {
            status: 'loading',
            symbols: []
        }
    },
);

export default store;
