function reducer(state, action) {
    let new_state;
    switch (action.type) {
        case UPDATE_SYMBOL_FIELD:
            let symbol = state.symbols.symbols.data.findIndex(
                ((action, symbol, index)=>{
                    // console.log(action);
                    return action.symbol === symbol.id;
                }).bind({}, action)
            );
            new_state = Object.assign({}, state);
            new_state.symbols.symbols.data[symbol][action.field] = action.value;
            break;
        case UPDATED_SYMBOLS:
            new_state = Object.assign({}, {
                symbols: {
                    status: action.status,
                    symbols: action.data,
                }
            })
            break;
        default:
            new_state = state;
            break;
    }
    return new_state
}

const UPDATE_SYMBOL_FIELD = 'UPDATE_SYMBOL_FIELD';
const UPDATED_SYMBOLS = 'UPDATED_SYMBOLS';

function updated_symbols(symbols, status='loaded'){
    return {
        type: UPDATED_SYMBOLS,
        data: symbols,
        status: status,
    }
}

function update_symbol (symbol, field, value) {
    return {
        type: UPDATE_SYMBOL_FIELD,
        symbol: symbol.id,
        field: field,
        value: value,
    }
}

export {
    updated_symbols,
    update_symbol,
    reducer,
};

// export default reducer;
