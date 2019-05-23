import { Component, AfterViewInit } from '@angular/core';
import { FormBuilder, FormGroup, FormControl, FormArray } from '@angular/forms';
import { AgFilterComponent } from 'ag-grid-angular';
import { IFilterParams, IDoesFilterPassParams } from 'ag-grid-community';
import { categories } from '../../services/entities';

@Component({
    templateUrl: './category-filter.html'
})
export class CategoryFilterComponent implements AgFilterComponent {
    form: FormGroup;
    params: IFilterParams;
    hidePopup?: Function;
    selectedCategories: string[];

    constructor(private formBuilder: FormBuilder) {
        this.selectedCategories = [];
        let controls = this.getCategories().map(_ => new FormControl(false));
        this.form = this.formBuilder.group({categories: new FormArray(controls)})
    }

    getCategories() { return categories; }

    onSubmit() {
        this.selectedCategories = this.form.value.categories
            .map((value, index) => value ? this.getCategories()[index] : null)
            .filter(value => value !== null);
        this.params.filterChangedCallback();
        this.hidePopup();
    }

    agInit(params: IFilterParams) {
        this.params = params;
    }

    isFilterActive(): boolean {
        return this.selectedCategories.length > 0;
    }

    doesFilterPass(params: IDoesFilterPassParams): boolean {
        return true;
    }

    getModel(): any {
        return this.selectedCategories;
    }

    setModel(model: any) {
        this.selectedCategories = model;
    }

    applyToAll(value: boolean): any {
        this.form['controls'].categories['controls'].forEach(function (item, i) {
            item.setValue(value);
        });
    }

    afterGuiAttached(params?: {hidePopup?: Function}) {
        this.hidePopup = params.hidePopup;
    }
}
