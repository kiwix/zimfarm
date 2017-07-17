import { Component, OnInit } from '@angular/core';

@Component({
    selector: 'dashboard',
    templateUrl: './dashboard.component.html',
    styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent {
    cards: Card[] = [];
    
    ngOnInit() {
        for (var i = 0; i < 5; i++) {
            let card = new Card();
            card.title = 'Task' + i;
            this.cards.push(card);
        }
    }
}

export class Card {
    title: string;
}