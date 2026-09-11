// HidePix Prank App Specification & Architecture
// Language: Conceptual C++ Specification
// Purpose: Funny prank demo with photo trap, memes, puzzles, and fake notifications
// Target Implementation: Python 3 + Tkinter (see hidepix.py)

#ifndef HIDEPIX_APP_HPP
#define HIDEPIX_APP_HPP

#include <string>
#include <vector>

/**
 * @brief Main Controller Class for HidePix Prank Demo
 * Matches 1-to-1 with the Python implementation in `hidepix.py`.
 */
class HidePixApp {
public:
    // --- Lifecycle & Initialization ---
    // HidePixApp(void* root_window);

    // --- Core Features ---

    /**
     * @brief Cartoon decorative UI front page.
     * - Pastel bubblegum cartoon theme
     * - DEMO MODE prominent warning badge
     * - Rounded emoji action buttons
     * - Photo preview center with comic vault frame
     */
    void FrontPage(); 

    /**
     * @brief The core trap: sets selected photo as desktop wallpaper.
     * - Uses Windows ctypes SystemParametersInfoW (SPI_SETDESKWALLPAPER)
     * - Fake notification toast: "Close Friends Alert"
     * - Asks for Close Friends emails (stored locally only, zero sending)
     * - Initiates 5-minute countdown lock
     */
    void HidePhotoTrap();

    /**
     * @brief Close friends management dialog.
     * - Add / remove email addresses
     * - Persists locally to friends_list.json
     * - Displays the Mystery: why emails are asked (pure comedic panic!)
     */
    void CloseFriendsSection();

    /**
     * @brief Wallpaper reset safety timer.
     * - Locks reset for 5 minutes (300 seconds)
     * - Background ticking countdown
     * - Before 5 min: triggers MemeScreens() refusal popup
     * - After 5 min: unlocks reset with celebratory Snake cartoon
     * - Includes ⚡ Demo Skip shortcut for live hackathon presentations
     * - Restores original wallpaper from Windows registry backup
     */
    void ResetTimer();

    /**
     * @brief Interactive trick puzzle during the 5-minute lock.
     * - Riddles and trick math questions
     * - If solved early: plays "Wow nice try!" voice
     * - Prank message: "It was fun... but still a prank! 🐍"
     * - Wallpaper is NOT reset early
     */
    void PuzzleTrap();

    /**
     * @brief Random cartoon meme screens when reset is attempted early.
     * - "Snake says: Sssstop rushing 🐍"
     * - "Error 418: I'm a teapot 🫖"
     * - "Separation Anxiety 🥺"
     */
    void MemeScreens();

    /**
     * @brief Cute voice-over sound player.
     * - Plays nope_voice.wav ("Nope! I'm not deleting that!")
     * - Plays wow_voice.wav ("Wow nice try!")
     * - Uses pygame.mixer with Windows winsound / SAPI fallback
     * - Replay voice button on front page
     */
    void CuteVoiceOver();

private:
    // --- Technical State (Implemented in Python) ---
    // std::string selected_photo_path;
    // std::string original_wallpaper_path;
    // std::vector<std::string> friends_emails;
    // int lock_duration_seconds = 300;
    // bool is_locked = false;
};

#endif // HIDEPIX_APP_HPP
