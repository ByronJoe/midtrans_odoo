odoo.define('odoo_midtrans.main', function(require)
{
    "use strict";
    var session = require('web.session');
    var scriptTag = document.createElement('script');

    $(document).ready(function(){
        if(window.location.pathname.indexOf('/shop/payment') > -1){
            session.rpc('/midtrans/get_snap_js').then(function(response){
                if(response.production == "1"){
                    var js = "https://app.midtrans.com/snap/snap.js";
                }else{
                    var js = "https://app.sandbox.midtrans.com/snap/snap.js";
                }

                scriptTag.src = js;
                scriptTag.setAttribute('data-client-key', response.client_key);
                document.head.appendChild(scriptTag);
            });
        }
    });

    function set_state_busy(is_busy)
    {
        if (is_busy)
        {
            $.blockUI();
        }
        else
        {
            if ($.blockUI) {
                $.unblockUI();
            }
        }
    }

    function get_form_data($el)
    {
        return $el.serializeArray().reduce(
                function(m,e){m[e.name] = e.value; return m;}, {});
    }

    function attach_event_listener(selector)
    {
        var $btn = $(selector),
            $form = $btn.parents('form'),
            $acquirer = $btn.closest('div.oe_sale_acquirer_button,div.oe_quote_acquirer_button,div.o_website_payment_new_payment'),
            acquirer_id = $("#acquirer_midtrans").val() || $acquirer.data('id') || $acquirer.data('acquirer_id');

        set_state_busy(true);
        var promise,promise2,formData = get_form_data($form);

        session.rpc('/midtrans/get_token', {
            acquirer_id:acquirer_id,
            order_id: formData['order_id'],
            amount: formData['amount'],
            reference: formData['reference'],
            return_url: formData['return_url']
        }).then(function(response){
            if (response.snap_errors)
            {
                alert(response.snap_errors.join('\n'));
                set_state_busy(false);
                return;
            }
            scriptTag.setAttribute('data-client-key', response.client_key);
            set_state_busy(false);
            window.snap.pay(response.snap_token,
            {
                onSuccess: function(result)
                {
                    session.rpc('/midtrans/validate', {
                        reference: result.order_id,
                        transaction_status: 'done',
                        message: result.status_message,
    
                    }).then(function()
                    {
                        window.location = '/shop/confirmation';
                    });
                },
                onPending: function(result)
                {
                    session.rpc('/midtrans/validate', {
                        reference: result.order_id,
                        transaction_status: 'pending',
                        message: result.status_message,
    
                    }).then(function()
                    {
                        window.location = '/shop/confirmation';
                    });
                },
                onError: function(result)
                {
                    session.rpc('/midtrans/validate', {
                        reference: result.order_id,
                        transaction_status: 'error',
                        message: result.status_message,
    
                    }).then(function()
                    {
                        window.location = '/shop/confirmation';
                    });
                },
                onClose: function()
                {
                    set_state_busy(false);
                }
            });
        });
    }

    odoo.odoo_midtrans = {
        attach: attach_event_listener,
    };
});
