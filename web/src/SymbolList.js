import React from 'react';
import api from './server_api';
import store from './store';
import {updated_symbols, update_symbol, reducer} from './redux_utils';

class SymbolList extends React.Component {
    update_symbols () {
        this.setState({
            status: 'loading',
        })
        api.api_method('/update/symbols', {
                method: 'POST'
            }
        ).then((function (data) {
            this.setState({
                status: 'loaded',
                symbols: data.data
            })
        }).bind(this)).catch((
            (error) => {
                console.error(error);
                this.setState({
                    status: 'loaded'
                })
            }
        ).bind(this))
    }

    constructor (props) {
        super(props)
        this.state = {
            status: 'loading',
            symbols: null,
        }
    }

    componentDidMount () {
        api.api_method('/list/symbols').then((
            (data) => {
                this.setState({
                    status: 'loaded',
                    symbols: data.data,
                });
            }
        ).bind(this)).catch((
            (error) => {
                console.error(error);
                this.setState({
                    status: 'error',
                })
            }
        ).bind(this));
    }

    update_field(symbol, field, value) {
        api.api_method(`/update/symbol/${symbol.id}`, {
            method: 'POST',
            data: JSON.stringify({
                [[field]]: value
            })
        }).then((function (data) {
            let symbols = this.state.symbols;
            let index = symbols.findIndex(
                (value) => (value.id === symbol.id)
            );
            symbols[index] = data.data;
            this.setState({
                symbols: symbols
            });
        }).bind(this)).catch((function (error) {
            console.error(error);
        }).bind(this))
    }

    render () {
        return (
            <div>
                {this.state.status === 'loading' && (
                    <h3>Loading</h3>
                )}
                {this.state.status === 'error' && (
                    <h3>Error</h3>
                )}
                {this.state.status === 'loaded' && (
                    <div className="list symbol_list">
                        <h2 className="main__site_title">Пары</h2>
                        <button
                            onClick={this.update_symbols.bind(this)}
                            className="button update_symbols"
                        >Подгрузить пары</button>
                        <div className="table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Главный тикер</th>
                                        <th>Котировочный тикер</th>
                                        <th>Название</th>
                                        <th>Описание</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {this.state.status === 'loaded' && (
                                        this.state.symbols.map((symbol, num) => (
                                            <Symbol
                                                key={symbol.first + '/' + symbol.second}
                                                symbol={symbol}
                                                update_field={(
                                                    (field, value) => {
                                                        this.update_field(symbol, field, value)
                                                    }
                                                ).bind(this)}
                                            ></Symbol>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        )
    }
}

class Symbol extends React.Component {
    make_field_editing (field, change_to=true) {
        if (change_to) {
            this.setState({
                editing_field: field,
            });
        } else {
            this.setState({
                editing_field: null,
            });
        }
    }
    constructor(props){
        super(props)
        this.state = {
            'editing_field': null,
        }
    }
    fields = [
        'first', 'second', 'name', 'short_description'
    ]

    render () {
        // console.log(this.props.entries);
        return (
            <tr>
                { this.fields.map(
                    ((field, index)=>
                        (<SymbolField
                            key={field}
                            make_editing={((change_to=true)=>{
                                this.make_field_editing(field, change_to)
                            }).bind(this)}
                            editing={this.state.editing_field === field}
                            field={field}
                            update_field={(
                                (value) => {
                                    this.props.update_field(field, value)
                                }
                            ).bind(this)}
                         >{this.props.symbol[field]}</SymbolField>)
                    ).bind(this)
                ) }
                {/* <td>
                    <button className="button delete_button" type="button">Delete</button>
                </td> */}
            </tr>
        )
    }
}

const EMPTY_FIELD = 'Empty';

class SymbolField extends React.Component{
    // function () {
    //     this.update_field.bind(this)
    // }
    update_field () {
        let value;
        value = this.input_ref.current.value;
        this.props.make_editing(false);
        this.props.update_field(value);
        // this.props.update_field(this.props.field, value);
    }
    constructor (props) {
        super(props)
        this.input_ref = React.createRef();
    }
    render () {
        if (this.props.editing){
            let value_default = this.props.children === EMPTY_FIELD ? '' : this.props.children;
            return (
                <td>
                    <div className="editing_field">
                        <textarea
                            ref={this.input_ref}
                            className="table_cell_editing_input"
                            name="{this.props.field}"
                            cols={value_default.length}
                            rows="1"
                            defaultValue={value_default}></textarea>
                        <button type="button" className="button save_button" onClick={this.update_field.bind(this)}>Save</button>
                    </div>
                </td>
            )
        } else {
            return (
                <td onClick={this.props.make_editing}>
                    <span>{this.props.children }</span>
                </td>
            )
        }
    }
}

export default SymbolList
