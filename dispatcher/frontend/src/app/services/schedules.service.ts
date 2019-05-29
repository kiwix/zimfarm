import { Injectable } from '@angular/core';
import { HttpClient, HttpInterceptor, HttpHeaders, HttpRequest, HttpHandler, HttpEvent } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import cronstrue from 'cronstrue';

import { getAPIRoot } from './config';
import { map } from 'rxjs/operators';

@Injectable({
    providedIn: 'root',
})
export class SchedulesService {
    constructor(private http: HttpClient) { }

    list(skip: number = 0, limit: number = 20, queues: string[] = [],
         categories: string[] = [], languages: string[] = [],
         name: string = "", tags: string[] = []) {
        let params = {
            skip: skip.toString(),
            limit: limit.toString()};
        if (queues.length > 0) {
            params['queue'] = queues;
        }
        if (categories.length > 0) {
            params['category'] = categories;
        }
        if (languages.length > 0) {
            params['lang'] = languages;
        }
        if (name.length > 0) {
            params['name'] = name;
        }
        if (tags.length > 0) {
            params['tag'] = tags;
        }
        return this.http.get<SchedulesListResponseData>(
            getAPIRoot() + '/schedules/', {params: params}
        ).pipe(map(data => {
            return data
        }))
    }

    get(schedule_id_name: string) {
        let url = getAPIRoot() + '/schedules/' + schedule_id_name
        return this.http.get<Schedule>(url);
    }
}

export interface SchedulesListResponseData {
    items: Array<Schedule>;
    meta: SchedulesListMeta;
}

export interface SchedulesListMeta {
    limit: number;
    skip: number;
    count: number;
}

export interface Schedule {
    _id: string;
    category: string;
    enabled: boolean;
    name: string;
    beat: Beat;
    config: Config;
    language: Language;
    tags: [string];
}

export class Beat {
    type: string;
    config: Object;

    constructor(type: string, config: Object) {
        this.type = type
        this.config = config
    }

    description(): string {
        if (this.type == 'crontab') {
            let minute = this.config['minute'] != null ? this.config['minute'] : '*'
            let hour = this.config['hour'] != null ? this.config['hour'] : '*'
            let day_of_week = this.config['day_of_week'] != null ? this.config['day_of_week'] : '*'
            let day_of_month = this.config['day_of_month'] != null ? this.config['day_of_month'] : '*'
            let month_of_year = this.config['month_of_year'] != null ? this.config['month_of_year'] : '*'
            return cronstrue.toString(Array(minute, hour, day_of_month, month_of_year, day_of_week).join(' '))
        } else {
            return '';
        }
    }
}

export interface Config {
    task_name: string;
    queue: string;
    warehouse_path: string;
    offliner: ConfigOffliner;
}

export interface ConfigOffliner {
    image_name: string;
    image_tag: string;
    flags: Object;
}

export interface Language {
    code: string;
    name_en: string;
    name_native: string;
}
