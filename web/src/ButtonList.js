import React from 'react';
import api from './server_api';
import { BUY, SELL } from './config';

export class ButtonList extends React.Component {

    delete_button(id) {
        api.api_method(`/delete/button/${id}`, {
            method: 'DELETE'
        }).then((
            (id, data) => {
                let new_buttons = this.state.buttons;
                let button_index = new_buttons.findIndex((
                    (id, button) => {
                        return (button.id) === id
                    }
                ).bind(this, id));
                new_buttons.splice(button_index, 1);
                this.setState({
                    buttons: new_buttons,
                });
            }
        ).bind(this, id)).catch((function (error) {
            console.error(error);
        }).bind(this));
    }

    constructor (props) {
        super(props);
        this.state = {
            status: 'loading',
        };
    }

    componentDidMount () {
        api.api_method('/list/buttons').then((
            (data) => {
                this.setState({
                    status: 'loaded',
                    buttons: data.data,
                })
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

    render () {
        return (
            <div className="button_list">
                { this.state.status === 'loaded' && (
                    <div>
                        <button
                            className="button add_new_button"
                            onClick={(
                                () => { this.props.change_page('new_button'); }
                            ).bind(this)}
                        >Новая кнопка</button>
                        <div className="table buttons_table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Тип операции</th>
                                        <th>Объем</th>
                                        <th className="th-preview">Предпросмотр</th>
                                        <th className="delete_column">D</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {this.state.buttons.map((
                                        (button) => (
                                            <tr key={button.id}>
                                                <td>{button.order_type.toString() === SELL ? 'Продажа' : 'Покупка' }</td>
                                                <td>{button.volume}</td>
                                                <td>
                                                    <QuickButton
                                                        button={button}
                                                        handle_click={()=>{}}
                                                    ></QuickButton>
                                                </td>
                                                <td>
                                                    <button
                                                        className="button delete_button"
                                                        type="button"
                                                        onClick={()=>{this.delete_button(button.id)}}
                                                    >Delete</button>
                                                </td>
                                            </tr>
                                        )
                                    ).bind(this))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
                { this.state.status === 'loading' && (
                    <h3>Loading</h3>
                )}
                { this.state.status === 'error' && (
                    <h3>Error</h3>
                )}
            </div>

        )
    }
}

export class NewButton extends React.Component {

    update_preview () {
        this.setState({
            button_preview: this.new_preview(),
        })
    }

    new_preview (options={}) {
        let form = this.form_ref.current;
        console.log(options.order_type || form.elements.order_type.value);
        let new_preview = {
            order_type: options.order_type || form.elements.order_type.value,
            volume: form.elements.volume.value,
        }
        return new_preview;
    }

    change_order_type(ot){
        let new_preview = this.new_preview({
            order_type: ot,
        });
        this.setState({
            chosen: ot,
            button_preview: new_preview,
        })
    }

    constructor (props){
        super(props)
        this.state = {
            chosen: BUY,
            button_preview: null,
        }
        this.form_ref = React.createRef();
    }

    handle_submit (event){
        var data = new FormData(this.form_ref.current);
        var new_button = {};
        data.forEach(function (item, key) {
            new_button[key] = item;
        });
        api.api_method('/post/button', {
                method: 'POST',
                data: JSON.stringify(new_button),
            }
        ).then((
            (data) => { this.props.change_page('list-buttons') }
        ).bind(this)).catch((
            (error) => { console.error(error) }
        ).bind(this));
        event.preventDefault();

    }

    render () {
        let choose_buttons;
        if (this.state.chosen === BUY) {
            choose_buttons = (
                <div className="form_buttons">
                    <button type="button" onClick={
                        ()=>{ this.change_order_type(BUY) }
                    } className="button order_choose_button buy_button chosen">Купить</button>
                    <button type="button" onClick={
                        ()=>{ this.change_order_type(SELL) }
                    } className="button order_choose_button sell_button">Продать</button>
                </div>
            )
        } else {
            choose_buttons = (
                <div className="form_buttons">
                    <button type="button" onClick={
                        ()=>{ this.change_order_type(BUY) }
                    } className="button order_choose_button buy_button">Купить</button>
                    <button type="button" onClick={
                        ()=>{ this.change_order_type(SELL) }
                    } className="button order_choose_button sell_button chosen">Продать</button>
                </div>
            )
        }
        return (
            <div className="new_quick_button">
                <div className="form">
                    <form ref={this.form_ref} onSubmit={this.handle_submit.bind(this)}>
                        <div className="form_field">
                            <label className="form_field-label" htmlFor="">Вид кнопки</label>
                            {choose_buttons}
                            <input
                                className="form_field-input"
                                type="hidden"
                                name="order_type"
                                value={this.state.chosen}
                            />
                        </div>
                        <div className="form_field">
                            <label className="form_field-label" htmlFor="">Объем</label>
                            <input onInput={this.update_preview.bind(this)} className="form_field-input" required type="text" name="volume"/>
                        </div>
                        <button className="button new_order_button" type="submit">Создать кнопку</button>
                    </form>
                    <div className="button_preview">
                        <h3 className="button_preview-h3">Предпросмотр:</h3>
                        { this.state.button_preview && (
                            <QuickButton
                                handle_click={()=>{}}
                                button={this.state.button_preview}
                            ></QuickButton>
                        ) }
                    </div>
                </div>
            </div>
         )
    }
}

export class QuickButton extends React.Component {
    constructor (props) {
        super(props)
    }
    render () {
        let button_class = this.props.button.order_type.toString() === SELL ? 'sell_button' : 'buy_button';
        let button_word = this.props.button.order_type.toString() === SELL ? 'Продать' : 'Купить';
        return (
            <div className="button_div">
                <button
                    className={ 'button quick_button ' + button_class }
                    onClick={ (
                        (button) => {
                            this.props.handle_click(button)
                        }
                    ).bind(this, this.props.button) }
                    type="button"
                >
                    <span className="quick_button-word">{ button_word }</span>
                    <span className="quick_button-for">за</span>
                    <span
                        className="quick_button-volume"
                    >
                        { this.props.button.volume }</span>
                    <span className="quick_button-dollar">$</span>
                </button>
            </div>
        )
    }
}
