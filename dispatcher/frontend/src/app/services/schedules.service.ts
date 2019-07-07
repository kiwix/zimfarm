import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { BaseService } from './base.service';

@Injectable({
    providedIn: 'root',
})
export class SchedulesService extends BaseService {
    constructor(private http: HttpClient) { super() }

    list(params: SchedulesListRequestParams) {
        return this.http.get<SchedulesListResponseData>(
            this.getAPIRoot() + '/schedules/', {params: params.toDict()})
    }

    list_old(skip: number = 0, limit: number = 20, queues: string[] = [], categories: string[] = [], 
        languages: string[] = [], name: string = "", tags: string[] = []) {
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
            this.getAPIRoot() + '/schedules/', {params: params})
    }

    get(schedule_id_name: string) {
        let url = this.getAPIRoot() + '/schedules/' + schedule_id_name
        return this.http.get<Schedule>(url);
    }
}

export class SchedulesListRequestParams {
    limit?: number;
    offset?: number;
    name?: string
    categories: Array<string> = [];

    constructor(limit: number = 200, offset: number = 0, filterData: any = {}) {
        this.limit = limit
        this.offset = offset
        this.name = filterData['search']
        if (filterData['categories']) {
            this.categories = Object.keys(filterData.categories).reduce((filtered, key) => {
                if (filterData['categories'][key]) {
                    filtered.push(key)
                }
                return filtered
            }, Array<string>())
        }
    }

    toDict(): {} {
        let params = {}
        if (this.limit) { params['limit'] = this.limit}
        if (this.offset) { params['offset'] = this.offset}
        if (this.name && this.name.length > 0) {params['name'] = this.name}
        if (this.categories.length > 0) {params['category'] = this.categories}
        return params
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
    config: Config;
    language: Language;
    tags: [string];
}

export interface Config {
    image: ConfigImage;
    task_name: string;
    queue: string;
    warehouse_path: string;
    flags: {};
}

export interface ConfigImage {
    name: string;
    tag: string;
}

export interface Language {
    code: string;
    name_en: string;
    name_native: string;
}
