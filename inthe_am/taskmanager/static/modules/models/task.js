var model = DS.Model.extend({
  annotations: DS.hasMany(App.Annotation),
  description: DS.attr('string'),
  due: DS.attr('date'),
  entry: DS.attr('date'),
  modified: DS.attr('date'),
  priority: DS.attr('string'),
  resource_uri: DS.attr('string'),
  start: DS.attr('date'),
  'status': DS.attr('string'),
  urgency: DS.attr('number'),
  uuid: DS.attr('string'),
  depends: DS.attr('string'),

  editable: function(){
    if (this.get('status') == 'pending') {
      return true;
    }
    return false;
  }.property('status'),

  icon: function(){
    if (this.get('status') == 'completed') {
      return 'fa-check-square-o';
    } else {
      return 'fa-square-o';
    }
  }.property('status', 'urgency'),

  dependent_tickets: function(){
    var value = this.get('depends');
    var values = [];
    if (value) {
      var ticket_ids = value.split(',');
      for(var i = 0; i < ticket_ids.length; i++) {
        values[values.length] = this.store.find('task', ticket_ids[i]);
      }
      return values;
    } else {
      return [];
    }
  }.property('depends')
});

module.exports = model;
