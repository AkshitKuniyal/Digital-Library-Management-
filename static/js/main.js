// Basic initialization code
document.addEventListener('DOMContentLoaded', function() {
    console.log('JavaScript loaded successfully');
    
    // Add any global JavaScript functionality here
    // For example, password confirmation validation:
    const password = document.getElementById('password');
    const confirm_password = document.getElementById('confirm_password');
    
    if (password && confirm_password) {
        function validatePassword() {
            if (password.value !== confirm_password.value) {
                confirm_password.setCustomValidity("Passwords don't match");
            } else {
                confirm_password.setCustomValidity('');
            }
        }
        
        password.onchange = validatePassword;
        confirm_password.onkeyup = validatePassword;
    }
});