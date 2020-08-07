import React from 'react';
import api from './server_api';

export class ImportExport extends React.Component {
    import_db () {
        let input = document.createElement('input');
        input.type = 'file';
        input.click();
        input.addEventListener('change', (() => {
            let file = input.files[0];
            let data = new FormData();
            data.append('file', file);
            api.api_method('/upload/db', {
                method: 'POST',
                data: data,
            });
        }).bind(this))
        // console.log(input);
    }

    export_db () {
        api.api_method('/download/db', {
            json: false,
        })
        .then(response => response.blob())
        .then(blob => {
            let url = window.URL.createObjectURL(blob);
            let a = document.createElement('a');
            a.href = url;
            a.download = "db.dump";
            document.body.appendChild(a);
            a.click();
            a.remove();
        });
    }

    render () {
        return (
            <div className="import-export">
                <button
                    className="menu__page_option-button"
                    type="button"
                    onClick={this.export_db}
                >
                    Скачать базу
                </button>
                <button
                    className="menu__page_option-button"
                    type="button"
                    onClick={this.import_db}
                >
                    Загрузить базу
                </button>
            </div>
        )
    }
}
