import { Component, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';

import { BeatConfig, CrontabBeatConfig } from '../../services/schedules.service';

@Component({
    selector: 'app-schedule-beat',
    templateUrl: './schedule-beat.component.html',
    styleUrls: ['./schedule-beat.component.css', '../schedule.shared.css']
})
export class ScheduleBeatComponent implements OnInit {
    name = new FormControl('')

    constructor() { }

    ngOnInit() {
    }

    config = new CrontabBeatConfig({})

    configChanged(): void {
        this.config.updateDescription()
        console.log(this.config)
    }
}
