$(document).ready(function () {
    check_checkboxes()

    $('#inventories-table').DataTable({
        "searching": true,
        paging: false,
        ordering: true,
        info: true,
        responsive: {
            details: false
        }
    });

    $(function () {
        $('[data-toggle="tooltip"]').tooltip()
    })

});

$("#cancel-delete-inventories-btn").on("click", function (e) {
    deselect_all_checkboxes("selected-item-")
    $("#collapseDeleteInventories").collapse("hide");
});

$('input:checkbox[id^="selected-item-"]').on("click", function (e) {
    check_checkboxes();
});

function check_checkboxes() {
    let number_selected = checkbox_count("selected-item-")

    let delete_collapse_btn_selector = $('#delete-inventories-btn-collapse');
    let delete_btn_selector = $('#delete-inventories-btn');
    let delete_span_selector = $('#delete-inventories-span');

    if (number_selected > 0) {
        delete_collapse_btn_selector.attr('href', '#collapseDeleteInventories');
        delete_btn_selector.css("pointer-events", "auto");
        delete_span_selector.css('color', 'red');
        delete_btn_selector.prop('disabled', false);
        delete_collapse_btn_selector.prop('disabled', false);
    } else {
        $("#collapseDeleteInventories").collapse("hide");
        delete_collapse_btn_selector.removeAttr('href');
        delete_btn_selector.css("pointer-events", "none");
        delete_span_selector.css('color', 'lightgray');
        delete_btn_selector.prop('disabled', true);
        delete_collapse_btn_selector.prop('disabled', true);
        delete_btn_selector.removeAttr('disabled');
    }
}


$('[id^=inventoryEdit]').click(function () {
    let inventory_id = $(this).attr('data-inventory-id');
    let inventory_name = $(this).attr('data-inventory-name');
    let inventory_desc = $(this).attr('data-inventory-description');
    let inventory_public = $(this).attr('data-inventory-public');

    $('#edit_form_inventory_id').val(inventory_id)
    $('#edit_form_inventory_name').val(inventory_name)
    $('#edit_form_inventory_description').val(inventory_desc)

    let inventory_public_is_checked = (inventory_public === "1")

    $('#edit_form_inventory_public').prop('checked', inventory_public_is_checked);

});

$("#confirm-delete-inventories-btn").on("click", function (e) {
    e.preventDefault();

    let selected_list = get_selected_checkbox_ids("selected-item-", "data-inventory-id")

    $.ajax({
        type: "POST",
        url: delete_inv_url,
        contentType: 'application/json;charset=UTF-8',
        headers: {
            "X-CSRFToken": csrf_token,
        },
        data: JSON.stringify(
            {
                'inventory_ids': selected_list,
                'username': username,
            }
        ),
        success: function () {
            location.reload();
        },
        error: function () {
            location.reload();
        }
    });
});