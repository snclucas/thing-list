/**
 * Counts the number of checked checkboxes that match the given selector.
 *
 * @param {string} checkbox_selector - The selector to match checkboxes.
 * @returns {number} - The number of checked checkboxes that match the selector.
 */
function checkbox_count(checkbox_selector) {

    let all_checkboxes = $('input:checkbox[id^="' + checkbox_selector + '"]')

    let number_selected  = 0;

    $.each(all_checkboxes, function () {
        let $this = $(this);
        if ($this.is(":checked")) {
            number_selected += 1
        }
    });

    return number_selected
}

function get_selected_checkbox_ids(checkbox_selector, id_selector) {

    let all_checkboxes = $('input:checkbox[id^=' + checkbox_selector + ']')
    let selected_list = [];

    $.each(all_checkboxes, function () {
        let $this = $(this);
        if ($this.is(":checked")) {
            selected_list.push($this.attr(id_selector));
        }
    });

    return selected_list
}

function deselect_all_checkboxes(checkbox_selector) {

    let all_checkboxes = $('input:checkbox[id^=' + checkbox_selector + ']')
    $.each(all_checkboxes, function () {
        let $this = $(this);
        $this.prop('checked', false);
    });

}
