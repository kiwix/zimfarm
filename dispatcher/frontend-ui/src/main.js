import Vue from 'vue'
Vue.config.productionTip = false;

// main dependencies
import VueRouter from 'vue-router'
import VueClipboard from 'vue-clipboard2'
import VueCookie from 'vue-cookie'
import axios from 'axios';
import filesize from 'filesize'

Vue.use(VueRouter);
Vue.use(VueClipboard);
Vue.use(VueCookie);

// Font Awesome
import { library } from '@fortawesome/fontawesome-svg-core'
import { faSpinner, faUser, faUserCircle, faKey, faTimes,
         faWrench, faSignInAlt, faSignOutAlt, faArrowCircleLeft,
         faCarrot, faHdd, faMicrochip, faMemory } from '@fortawesome/free-solid-svg-icons'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
library.add(faKey);
library.add(faHdd);
library.add(faUser);
library.add(faTimes);
library.add(faCarrot);
library.add(faMemory);
library.add(faWrench);
library.add(faSpinner);
library.add(faMicrochip);
library.add(faSignInAlt);
library.add(faSignOutAlt);
library.add(faUserCircle);
library.add(faArrowCircleLeft);
Vue.component('font-awesome-icon', FontAwesomeIcon);

// Multiselect for schedules filter
import Multiselect from 'vue-multiselect'
Vue.component('multiselect', Multiselect)

// tooltip for hover on loader table heads and durations
import Tooltip from 'vue-directive-tooltip';
import 'vue-directive-tooltip/dist/vueDirectiveTooltip.css';
Vue.use(Tooltip);

// Own modules
import App from './App.vue'
import Constants from './constants.js'
import routes from './routes'
import store from './store'  // Vuex store

// Own filters
Vue.filter('filesize', function(value) {
  if (!value)
    return '';
  return filesize(value);
});
Vue.filter('datetime', Constants.datetime);

// router
const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  linkActiveClass: "active",
  linkExactActiveClass: "exact-active",
  routes:routes,
})

new Vue({
  store: store,
  router: router,
  computed: {
      axios: function () { // prefixed axios object with API url and token from store
        return axios.create({
            baseURL: Constants.zimfarm_webapi,
            headers: {'Authorization': "Token " + store.getters.access_token},
            paramsSerializer: Constants.params_serializer,
          });
      }
  },
  render: h => h(App),
}).$mount('#app')
