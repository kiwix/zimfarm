<!-- Filterable list of schedules with filtered-fire button -->

<template>
  <div class="container">
    <nav class="row">
      <div class="col-sm-12 col-md-6 col-lg">
        <input type="text" class="form-control" v-model="selectedName" @change="loadSchedules" placeholder="Name…" />
      </div>
      <div class="col-sm-12 col-md-6 col-lg">
        <multiselect v-model="selectedCategoriesOptions"
                     :options="categoriesOptions"
                     :multiple="true"
                     :clear-on-select="true"
                     :preserve-search="true"
                     :searchable="true"
                     :closeOnSelect="true"
                     placeholder="Categories"
                     label="name"
                     track-by="value"
                     @input="loadSchedules">

        </multiselect>
      </div>
      <div class="col-sm-12 col-md-6 col-lg">
        <multiselect v-model="selectedLanguagesOptions"
                     :options="languagesOptions"
                     :multiple="true"
                     :clear-on-select="true"
                     :preserve-search="true"
                     :searchable="true"
                     :closeOnSelect="true"
                     placeholder="Languages"
                     label="name"
                     track-by="value"
                     @input="loadSchedules">

        </multiselect>
      </div>
      <div class="col-sm-12 col-md-6 col-lg">
        <multiselect v-model="selectedTagsOptions"
                     :options="tagsOptions"
                     :multiple="true"
                     :clear-on-select="true"
                     :preserve-search="true"
                     :searchable="true"
                     :closeOnSelect="true"
                     placeholder="Tags"
                     label="name"
                     track-by="value"
                     @input="loadSchedules">

        </multiselect>
      </div>
    </nav>
    <table v-if="schedules.length" class="table table-responsive-md table-striped table-hover table-bordered">
      <caption>Showing max. <select v-model="selectedLimit" @change.prevent="limitChanged">
          <option v-for="limit in limits" :key="limit" :value="limit">{{ limit }}</option>
        </select> out of <strong>{{ total_results }} results</strong>
        <RequestSelectionButton :for_name="selectedName"
                                :for_categories="selectedCategories"
                                :for_languages="selectedLanguages"
                                :for_tags="selectedTags"
                                :count="meta.count" />
        <b-button size="sm"
                  variant="secondary"
                  style="float:right;"
                  @click.prevent="clearSelection"
                  class="mr-1">clear <font-awesome-icon icon="times-circle" size="sm"/>
        </b-button>
      </caption>
      <thead class="thead-dark">
        <tr><th>Name</th><th>Category</th><th>Language</th><th>Offliner</th>
            <th v-tooltip="'Requested?'"><font-awesome-icon icon="clock"/></th><th colspan="2">Last Task</th></tr>
      </thead>
      <tbody>
        <tr v-for="schedule in schedules" :key="schedule._id">
          <td>
            <router-link :to="{name: 'schedule-detail', params: {'schedule_name': schedule.name}}">
              {{ schedule.name }}
            </router-link>
          </td>
          <td>{{ schedule.category }}</td>
          <td>{{ schedule.language.name_en }}</td>
          <td>{{ schedule.config.task_name }}</td>
          <td><font-awesome-icon v-if="has_requested_task(schedule.name)" icon="check"/></td>
          <td v-if="schedule.most_recent_task">
            <code :class="statusClass(schedule.most_recent_task.status)">{{ schedule.most_recent_task.status }}</code>
          </td>
          <td colspan="2" v-else>-</td>
          <td v-if="schedule.most_recent_task">
            <TaskLink :_id="schedule.most_recent_task._id" :updated_at="schedule.most_recent_task.updated_at" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script type="text/javascript">
  import Multiselect from 'vue-multiselect'

  import Constants from '../constants.js'
  import ZimfarmMixins from '../components/Mixins.js'
  import RequestSelectionButton from '../components/RequestSelectionButton.vue'
  import TaskLink from '../components/TaskLink.vue'

  export default {
    name: 'SchedulesList',
    mixins: [ZimfarmMixins],
    components: {Multiselect, RequestSelectionButton, TaskLink},
    data() {
      return {
        error: null,  // API originated error message
        meta: {}, // API query metadata (count, skip, limit)
        schedules: [],  // list of schedules returned by the API
        requested_tasks: [],  // list of schedule_names with requested tasks
      };
    },
    computed: {
      selectedLanguagesOptions: {  // multiple-select value for selected languages to filter on (union)
        set(selectedLanguagesOptions) {
          this.$store.commit('SET_SELECTED_LANGUAGES_OPTIONS', selectedLanguagesOptions);
          this.update_url();
        },
        get() {
          return this.$store.state.selectedLanguagesOptions;
        }
      },
      selectedCategoriesOptions: {  // multiple-select value for selected languages to filter on (union)
        set(selectedCategoriesOptions) {
          this.$store.commit('SET_SELECTED_CATEGORIES_OPTIONS', selectedCategoriesOptions);
          this.update_url();
        },
        get() {
          return this.$store.state.selectedCategoriesOptions;
        }
      },
      selectedTagsOptions: {  // multiple-select value for selected tags to filter on (intersection)
        set(selectedTagsOptions) {
          this.$store.commit('SET_SELECTED_TAGS_OPTIONS', selectedTagsOptions);
          this.update_url();
        },
        get() {
          return this.$store.state.selectedTagsOptions;
        }
      },
      selectedName: {  // entered regexp to match schedule names on
        set(selectedName) {
          this.$store.commit('SET_SELECTED_NAME', selectedName);
          this.update_url();
        },
        get() {
          return this.$store.state.selectedName;
        }
      },
      selection() { return this.schedules.map(function (schedule){ return schedule.name; }); },
      total_results() {
        return (this.meta && this.meta.count) ? this.meta.count : 0;
      },
      categoriesOptions() {
        let options = [];
        for (var i=0; i<this.categories.length; i++){
          options.push({name: this.categories[i], value: this.categories[i]});
        }
        return options;
      },
      selectedCategories() { return this.selectedCategoriesOptions.map((x) => x.value); },
      languagesOptions() {
        let options = [];
        for (var i=0; i<this.languages.length; i++){
          options.push({name: this.languages[i].name_en, value: this.languages[i].code});
        }
        return options;
      },
      selectedLanguages() { return this.selectedLanguagesOptions.map((x) => x.value); },
      tagsOptions() {
        let options = [];
        for (var i=0; i<this.tags.length; i++){
          options.push({name: this.tags[i], value: this.tags[i]});
        }
        return options;
      },
      selectedTags() { return this.selectedTagsOptions.map((x) => x.value); },
    },
    methods: {
      has_requested_task(schedule_name) { return this.requested_tasks.indexOf(schedule_name) != -1;},
      clearSelection() {
        this.selectedName = "";
        this.selectedCategoriesOptions = [];
        this.selectedLanguagesOptions = [];
        this.selectedTagsOptions = [];
        this.loadSchedules();
      },
      limitChanged() {
        this.saveLimitPreference(this.selectedLimit);
        this.loadSchedules();
      },
      update_url(){
         // updating url on reloading page
         if (this.selectedName.length > 0 ) {
            this.$router.replace({ name:"schedules-list", query:{ Categories:this.selectedCategories, Languages:this.selectedLanguages, Tags:this.selectedTags, name:this.selectedName }});
          }
          else {
            this.$router.replace({ name:"schedules-list" ,query:{ Categories:this.selectedCategories, Languages:this.selectedLanguages, Tags:this.selectedTags }});
          }
      },
      loadSchedules() {  // load filtered schedules from API
        let parent = this;
        this.toggleLoader("fetching recipes…");
        let params = {limit: parent.selectedLimit};

        // adding filters to url 
        [["Categories","category"], ["Languages","lang"], ["Tags","tag"]].forEach(function (key) {
        if (parent.$route.query[key[0]]) {
          params[key[1]] = parent.$route.query[key[0]];
            if (parent["selected"+key[0]+"Options"].length == 0) {
              if (typeof parent.$route.query[key[0]] === "string") {
                parent["selected"+key[0]+"Options"].push({ name:parent.$route.query[key[0]], value:parent.$route.query[key[0]] })
              }
              else {
                for(var i=0; i<parent.$route.query[key[0]].length; i++) {
                  parent["selected"+key[0]+"Options"].push({ name:parent.$route.query[key[0]][i], value:parent.$route.query[key[0]][i] });
                }
              }
            }
          }
        });
        if (this.$route.query.name) {
          params.name = this.$route.query.name;
          if (this.selectedName.length == 0) {
              this.selectedName = this.$route.query.name;
          }
        }
        parent.error = null;
        parent.queryAPI('get', '/schedules/', {params: params})
          .then(function (response) {
                parent.schedules = [];
                parent.meta = response.data.meta;
                parent.schedules = response.data.items;
                
                parent.queryAPI('get', '/requested-tasks/', {params: {
                    limit: parent.selectedLimit,
                    'schedule_name': parent.selection}})
                  .then(function (response) {
                    parent.requested_tasks = response.data.items.map((item) => {
                      return item["schedule_name"];
                    });
                  })
                  .catch(function () {
                    parent.requested_tasks = [];
                  })
          })
          .catch(function (error) {
            parent.schedules = [];
            parent.error = Constants.standardHTTPError(error.response);
          })
          .then(function () {
            parent.toggleLoader(false);
          });
      },
    },
    beforeMount() {
      this.loadSchedules();
    },
  }
</script>

<style type="text/css" scoped>
  .container table.table {
    margin-top: .5rem;
  }
  .container input[type=text] {
    height: 100%;
  }
  .col-sm-12 {
    margin-bottom: .25rem;
  }
</style>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>