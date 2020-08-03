import React from 'react';
import api from './server_api';
import { QuickButton } from './ButtonList';
import { BUY, SELL } from './config';


class OrderList extends React.Component {

    delete_order(id) {
        api.api_method(`/delete/order/${id}`, {
            method: 'DELETE'
        }).then((
            (id, data) => {
                let new_orders = this.state.orders;
                let order_index = new_orders.findIndex((
                    (id, order) => {
                        return (order.id) === id
                    }
                ).bind(this, id));
                new_orders.splice(order_index, 1);
                this.setState({
                    orders: new_orders,
                });
            }
        ).bind(this, id)).catch((function (error) {
            console.error(error);
        }).bind(this));
    }
    sort_by_field (field) {
        this.setState(function (state, props) {
            let asc = true;
            if (state.sorted && state.sort_field === field) {
                asc = !state.asc;
            }
            let orders = state.orders.slice(0);
            orders = orders.sort(function (order_a, order_b) {
                let field_a = order_a[field], field_b = order_b[field];
                if (field_a > field_b) return 1;
                if (field_a === field_b) return 0;
                if (field_a < field_b) return -1;
            })
            if (!asc) orders.reverse();
            return {
                orders: orders,
                sorted: true,
                sort_field: field,
                asc: asc,
            };
        })
    }

    new_order () {
        this.props.change_page('new_order')
    }
    constructor (props) {
        super(props)
        this.state = {
            status: 'loading',
            sorted: false,
            orders: [],
        }

        api.api_method('/list/orders').then((function (data) {
            let new_state = Object.assign({}, this.state);
            new_state = {
                status: 'loaded',
                orders: data.data,
            }
            this.setState(new_state)
        }).bind(this)).catch((function (error) {
            let new_state = this.state
            new_state = {
                status: 'error'
            }
            this.setState(new_state)
            console.error(error);
        }).bind(this))
    }

    componentDidMount () {
    }

    componentWillUnmount(){
    }

    render () {
        let orders;

        let header2 = (
            this.props.symbol ? (this.props.symbol.first + '/' + this.props.symbol.second) : 'Ордеры'
        )

        orders = this.state.orders.slice(0);
        if (this.props.symbol) {
            orders = orders.filter((function (order) {
                return order.symbol === (this.props.symbol.first + '/' + this.props.symbol.second)
            }).bind(this))
        }
        return (
            <div>
                { this.state.status === 'loaded' && (
                    <div className="list order_list">
                        <h2 className="main__site_title">{header2}</h2>
                        {this.props.symbol && (
                            <div ref={this.exchange_ref} className="exchange">
                                {this.state.exchange_rate ? (
                                    <h3>{this.state.exchange_rate + ' ' + this.props.symbol.second}</h3>
                                ) : (
                                    <h3>Курс еще не подгрузился</h3>
                                )}
                            </div>
                        )}
                        <button type="button" className="button add_order_button" onClick={this.new_order.bind(this)}>Новый ордер</button>
                        <div className="table">
                            <table>
                                <thead>
                                    <tr>
                                        <th onClick={
                                            () => {
                                                this.sort_by_field('symbol')

                                            }
                                        }>
                                            <span>Пара</span>
                                            <i className="sort_button fas fa-sort"></i>
                                        </th>
                                        <th onClick={
                                            () => {
                                                this.sort_by_field('order_type')
                                            }
                                        }>
                                            <span>Тип ордера</span>
                                            <i className="sort_button fas fa-sort"></i>
                                        </th>
                                        <th onClick={
                                            () => {
                                                this.sort_by_field('trigger_price')
                                            }
                                        }>
                                            <span>Триггерная цена</span>
                                            <i className="sort_button fas fa-sort"></i>
                                        </th>
                                        <th onClick={
                                            () => {
                                                this.sort_by_field('price')
                                            }
                                        }>
                                            <span>Целевая цена</span>
                                            <i className="sort_button fas fa-sort"></i>
                                        </th>
                                        <th onClick={
                                            () => {
                                                this.sort_by_field('volume')
                                            }
                                        }>
                                            <span>Объем</span>
                                            <i className="sort_button fas fa-sort"></i>
                                        </th>
                                        <th className="delete_column">D</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {this.state.status === 'loaded' && (
                                        orders.map(
                                            (function (order, num) {
                                                return (
                                                    <Order
                                                        key={order.id.toString()}
                                                        order={order}
                                                        delete_order={
                                                            this.delete_order.bind(this)
                                                        }
                                                    ></Order>
                                                )
                                            }).bind(this)
                                        ))
                                    }
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
                {this.state.status === 'loading' && (
                    <h3>Loading</h3>
                )}
                {this.state.status === 'error' && (
                    <h3>Error</h3>
                )}
            </div>
        )
    }
}

class Order extends React.Component {
    constructor(props){
        super(props)
        this.order = props.order;

    }
    render() {
        return (
            <tr>
                <td>{this.order.symbol}</td>
                <td>{this.order.order_type.toString() === BUY ? 'Покупка' : 'Продажа'}</td>
                <td>{this.order.trigger_price}</td>
                <td>{this.order.price}</td>
                <td>{this.order.volume + ' ' + this.order.symbol.split('/')[0]}</td>
                <td>
                    <button className="button delete_button" type="button" onClick={()=>{this.props.delete_order(this.order.id)}}>Delete</button>
                </td>
            </tr>
        )
    }
}

export class NewOrder extends React.Component {

    list_buttons (per_row=3) {
        let new_buttons = [];
        for (let i = 0; i < Math.ceil(
            this.state.buttons.length / per_row
        ); i++) {
            let subarray = this.state.buttons.slice(
                i * per_row, i * per_row + per_row
            );
            new_buttons.push(subarray);
        }
        return new_buttons;
    }

    handle_quick_button (button) {
        let form = this.form_ref.current;
        form.volume.value = button.volume;
        this.change_order_type(button.order_type.toString());
    }

    change_symbol (event) {
        let form = this.form_ref.current;
        let select = form.querySelector('.select_symbol select');
        this.setState({
            symbol_chosen: select.value,
        });
    }

    new_order_type (ot) {
        return {
            chosen: ot
        }
    }
    change_order_type(ot){
        this.setState(this.new_order_type(ot))
    }
    constructor (props){
        super(props);
        let symbol_chosen;
        if (this.props.symbol) {
            symbol_chosen = this.props.symbol;
        } else {
            symbol_chosen = null;
        }
        this.state = {
            chosen: BUY,
            symbols: null,
            buttons: null,
            status: 'loading',
            symbol_chosen: symbol_chosen,
        }

        let symbols_fetch = api.api_method('/list/symbols');
        let buttons_fetch = api.api_method('/list/buttons');


        symbols_fetch.then((
            (data) => {
                let symbol_chosen = data['data'];
                if (symbol_chosen.length >= 0) {
                    symbol_chosen = symbol_chosen[0].first + '/' + symbol_chosen[0].second
                    this.setState(
                        (state, props) => {
                            let new_status;
                            if (state.status === 'error') {
                                new_status = 'error';
                            } else {
                                new_status = state.status === 'preloaded' ? 'loaded' : 'preloaded';
                            }
                            return {
                                symbols: data['data'],
                                status: new_status,
                                symbol_chosen: symbol_chosen,
                            }
                    });
                } else {
                    this.setState({
                        status: 'no_symbols'
                    });
                }
            }
        ).bind(this)).catch((
            (error) => {
                let new_state = this.state
                this.setState({
                        status: 'error',
                });
                console.error(error);
            }
        ).bind(this));

        buttons_fetch.then((
            (data) => {
                data = data.data;
                this.setState(
                    (state, props) => {
                        let new_status;
                        if (state.status === 'error') {
                            new_status = 'error';
                        } else {
                            new_status = state.status === 'preloaded' ? 'loaded' : 'preloaded';
                        }
                        return {
                            buttons: data,
                            status: new_status,
                        }
                });
            }
        ).bind(this)).catch((
            (error) => {
                let new_state = this.state;
                this.setState({
                    status: 'error',
                });
                console.error(error);
            }
        ).bind(this));

        this.form_ref = React.createRef();
    }

    handle_submit (event){
        var data = new FormData(this.form_ref.current);
        var new_order = {};
        data.forEach(function (item, key) {
            new_order[key] = item;
        });
        api.api_method('/post/order', {
                method: 'POST',
                data: JSON.stringify(new_order),
            }
        ).then((function (data) {
            this.props.change_page('list-orders')
        }).bind(this));
        event.preventDefault();

    }

    render () {
        let choose_buttons;
        if (this.state.chosen === BUY) {
            choose_buttons = (
                <div className="form_buttons">
                    <button
                        type="button"
                        onClick={()=>{ this.change_order_type(BUY) }}
                        className="button order_choose_button buy_button chosen"
                    >
                        <span>Купить</span>
                    </button>
                    <button
                        type="button"
                        onClick={()=>{ this.change_order_type(SELL) }}
                        className="button order_choose_button sell_button"
                    >
                        <span>Продать</span>
                    </button>
                </div>
            )
        } else {
            choose_buttons = (
                <div className="form_buttons">
                    <button
                        type="button"
                        onClick={()=>{ this.change_order_type(BUY) }}
                        className="button order_choose_button buy_button"
                    >
                        <span>Купить</span>
                    </button>
                    <button
                        type="button"
                        onClick={()=>{ this.change_order_type(SELL) }}
                        className="button order_choose_button sell_button chosen"
                    >
                        <span>Продать</span>
                    </button>
                </div>
            )
        }

        return (
            <div className="form">
                {this.state.status === 'no_symbols' && (<h3>Добавьте пару валют</h3>)}
                { ['loading', 'preloaded'].includes(this.state.status) && (
                    <h3>Loading</h3>
                ) }
                {this.state.status === 'error' && (<h3>Ошибка доступа к серверу</h3>)}
                {this.state.status === 'loaded' && (
                    <form ref={this.form_ref} onSubmit={this.handle_submit.bind(this)}>
                        <div className="form_field select_symbol">
                            <label className="form_field-label" htmlFor="symbol">Пара</label>
                            <select className="form_field-input form_field-select" name="symbol" id="symbol" onChange={
                                (event)=>{this.change_symbol(event)}
                            }>
                                { this.state.symbols.map(
                                    (symbol, index) => (
                                        <option key={symbol.first + '/' + symbol.second} value={symbol.first + '/' + symbol.second} chosen={(
                                            this.state.symbol_chosen === (symbol.first + '/' + symbol.second) ? 'on' : 'off'
                                        )}>{symbol.first + '/' + symbol.second}</option>
                                    )
                                ) }
                            </select>
                        </div>
                        <div className="form_field" style={{display:'none'}}>
                            <label className="form_field-label" htmlFor="">Вид ордера</label>
                            {choose_buttons}
                            <input className="form_field-input" type="hidden" name="order_type" value={this.state.chosen}/>
                        </div>
                        <div className="form_field">
                            <label className="form_field-label" htmlFor="">Триггерная цена</label>
                            <input className="form_field-input" required type="text" name="trigger_price"/>
                        </div>
                        <div className="form_field">
                            <label className="form_field-label" htmlFor="">Целевая цена</label>
                            <input className="form_field-input" required type="text" name="price"/>
                        </div>
                        <div className="form_field">
                            <label className="form_field-label" htmlFor="">Объем</label>
                            <input className="form_field-input" required type="text" name="volume"/>
                        </div>
                        <div className="quick_buttons">
                            {/* { this.state.buttons.map((
                                (button, i) => {
                                    return (

                                    )
                                }
                            ).bind(this)) } */}
                            { this.list_buttons(3).map((
                                (row, i) => (
                                    <div
                                        className="quick_buttons_row"
                                        key={ i.toString() }
                                    >
                                        {row.map((
                                            (button) => (
                                                <QuickButton
                                                    handle_click={
                                                        this.handle_quick_button.bind(this)
                                                    }
                                                    key={button.id}
                                                    button={button}
                                                ></QuickButton>
                                            )
                                        ).bind(this))}
                                    </div>
                                )
                            ).bind(this)) }
                        </div>
                        <button className="button new_order_button" type="submit">Создать ордер</button>
                    </form>
                )}
            </div>
         )
    }
}

export default OrderList;
