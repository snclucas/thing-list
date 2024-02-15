$(document).ready(function () {

    tinymce.init({
        selector: 'textarea#form_item_description',
        height: 300,
        theme: 'modern',
        menubar: false,
        plugins: [
            'advlist lists link hr pagebreak',
            'searchreplace wordcount code',
            'nonbreaking table',
            'paste textcolor textpattern'
        ],
        toolbar1: 'bold italic | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent',
        image_advtab: false
    });

    $('#item-field-table').DataTable({
        "searching": true,
        paging: false,
        ordering: true,
        info: true,
        "pageLength": -1,
    });

});

$("#search-box").keyup(function () {
        $.ajax({
            type: "GET",
            url: user_items_url + "?query=" + $(this).val(),
            data: 'keyword=' + $(this).val(),
            beforeSend: function () {
                $("#search-box").css("background", "#FFF");
            },
            success: function (data) {
                $("#suggesstion-box").show();
                $("#suggesstion-box").html(data);
                $("#search-box").css("background", "#FFF");
            }
        });
    });

$("#save-fields-btn").on("click", function (e) {
    e.preventDefault();
    // clear the search table to make sure the table is complete
    let table = $('#item-field-table').DataTable();
    table.search('').draw();

    let all_checkboxes = $('input:checkbox[id^="selected-field-"]')
    let number_selected = [];
    $.each(all_checkboxes, function () {
        let $this = $(this);
        if ($this.is(":checked")) {
            number_selected.push(parseInt($this.attr('data-itemfield-id')));
        }
    });

    $.ajax({
        type: "POST",
        url: edit_item_url,
        contentType: 'application/json;charset=UTF-8',
        headers: {
            "X-CSRFToken": csrf_token,
        },
        data: JSON.stringify(
            {
                'field_ids': number_selected,
                'item_id': item_id,
                'inventory_slug': inventory_slug,
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

$('#masonry').imagesLoaded(function () {

    $('#masonry').masonry({
        itemSelector: '.item',
        gutter: 20,
        fitWidth: true,
        //percentPosition: true,
        originTop: true
    });

});

$(".image-checkbox").each(function () {
    if ($(this).find('input[types="checkbox"]').first().attr("checked")) {
        $(this).addClass('image-checkbox-checked');
    } else {
        $(this).removeClass('image-checkbox-checked');
    }
});

$(".image-checkbox").on("click", function (e) {
    $(this).toggleClass('image-checkbox-checked');
    var $checkbox = $(this).find('input[types="checkbox"]');
    $checkbox.prop("checked", !$checkbox.prop("checked"))


    let selectedImages = $('.image-checkbox-checked')

    if (selectedImages.length > 0) {
        $('#btn-remove-images').prop('disabled', false);
    } else {
        $('#btn-remove-images').prop('disabled', true);
    }

    if (selectedImages.length === 1) {
        $('#btn-main-image').prop('disabled', false);
    } else {
        $('#btn-main-image').prop('disabled', true);
    }

    e.preventDefault();
});

$("#btn-main-image").click(function (e) {
    e.preventDefault();

    let selectedImages = $('.image-checkbox-checked')
    let selectedImagesList = []
    for (const im of selectedImages) {
        selectedImagesList.push(im.getAttribute("data-image-url"));
    }
    let main_image = selectedImagesList[0]

    $.ajax({
        type: "POST",
        url: set_main_image_url,
        contentType: 'application/json;charset=UTF-8',
        headers: {
            "X-CSRFToken": csrf_token,
        },
        data: JSON.stringify(
            {
                'item_id': item_id,
                'item_slug': item_slug,
                'inventory_slug': inventory_slug,
                'username': username,
                'main_image': main_image
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

$("#btn-remove-images").click(function (e) {
    e.preventDefault();

    let selectedImages = $('.image-checkbox-checked')
    let selectedImagesList = []
    for (const im of selectedImages) {
        selectedImagesList.push(im.id);
    }

    $.ajax({
        type: "POST",
        url: delete_images_url,
        contentType: 'application/json;charset=UTF-8',
        headers: {
            "X-CSRFToken": csrf_token,
        },
        data: JSON.stringify(
            {
                'item_id': item_id,
                'item_slug': item_slug,
                'inventory_slug': inventory_slug,
                'username': username,
                'image_id_list': selectedImagesList
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

$('[id^="delete-related-"]').click(function (e) {
    e.preventDefault();

    let item1 = $(this).attr('data-item1-id');
    let item2 = $(this).attr('data-item2-id');

    $.ajax({
        type: "POST",
        url: unrelate_items_url,
        contentType: 'application/json;charset=UTF-8',
        headers: {
            "X-CSRFToken": csrf_token,
        },
        data: JSON.stringify(
            {
                'item1': item1,
                'item2': item2,
                'inventory_slug': inventory_slug,
                'username': username
            }
        ),
        success: function (e) {
            location.reload();
        },
        error: function (e) {
            location.reload();
        }
    });
});

const autoCompleteJS = new autoComplete({
    selector: "#autoComplete",
    placeHolder: "Search for Food...",
    data: {
        src: async (query) => {
            try {
                // Fetch Data from external Source
                const source = await fetch(user_item_types_url + `?query=${query}`);
                // Data should be an array of `Objects` or `Strings`
                const data = await source.json();

                return data;
            } catch (error) {
                return error;
            }
        },
        // Data source 'Object' key to be searched
        //keys: ["food"]
    },
    threshold: 0,
    resultsList: {
        element: (list, data) => {
            if (!data.results.length) {
                // Create "No Results" message element
                const message = document.createElement("div");
                // Add class to the created element
                message.setAttribute("class", "no_result");
                // Add message text content
                message.innerHTML = `<span>Save to add new type "${data.query}"</span>`;
                // Append message element to the results list
                list.prepend(message);
            }
        },
        noResults: true,
        maxResults: undefined,
    },
    resultItem: {
        highlight: true,
    },
    events: {
        input: {
            selection: (event) => {
                const selection = event.detail.selection.value;
                autoCompleteJS.input.value = selection;
            }
        }
    }
});

const autoCompleteJS44 = new autoComplete({
    selector: "#relateditem",
    placeHolder: "Search for items ... ",
    data: {
        src: async (query) => {
            try {
                // Fetch Data from external Source
                const source = await fetch(user_items_url + `?query=${query}`);
                // Data should be an array of `Objects` or `Strings`
                const data = await source.json();
                console.log(data);
                return data;
            } catch (error) {
                return error;
            }
        }
    },
    threshold: 0,
    autoFill: true,
    resultsList: {
        element: (list, data) => {
            if (!data.results.length) {
                // Create "No Results" message element
                const message = document.createElement("div");
                // Add class to the created element
                message.setAttribute("class", "no_result");
                // Add message text content
                message.innerHTML = `<span>Save to add new type "${data.query}"</span>`;
                // Append message element to the results list
                list.prepend(message);
            }
        },
        noResults: false,
        maxResults: undefined,
    },
    resultItem: {
        highlight: true,
    },
    events: {
        input: {
            selection: (event) => {
                const selection = event.detail.selection.value;
                autoCompleteJS44.input.value = selection;
            }
        }
    }
});
