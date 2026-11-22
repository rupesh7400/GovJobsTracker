package app.govjobs.tracker.ui

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument

@Composable
fun AppNav() {
    val nav = rememberNavController()
    NavHost(nav, startDestination = "splash") {
        composable("splash") { SplashScreen(nav) }
        composable("onboarding") { OnboardingScreen(nav) }
        composable("home") { HomeScreen(nav) }
        composable("latest") { LatestJobsScreen(nav) }
        composable("notifications") { AllNotificationsScreen(nav) }
        composable("categories") { CategoryVacanciesScreen(nav) }
        composable("results") { ResultsScreen(nav) }
        composable("admit") { AdmitCardsScreen(nav) }
        composable("answerkeys") { AnswerKeysScreen(nav) }
        composable("examupdates") { ExamUpdatesScreen(nav) }
        composable("deadlines") { DeadlinesScreen(nav) }
        composable("orgs") { OrganizationsScreen(nav) }
        composable("search") { SearchScreen(nav) }
        composable("recs") { RecResultsScreen(nav) }
        composable("saved") { SavedScreen(nav) }
        composable("subs") { SubscriptionsScreen(nav) }
        composable("history") { HistoryScreen(nav) }
        composable("settings") { SettingsScreen(nav) }
        composable("sources") { SourcesScreen(nav) }
        composable("more") { MoreScreen(nav) }
        composable("detail/{id}", listOf(navArgument("id") { type = NavType.LongType })) {
            DetailScreen(nav, it.arguments!!.getLong("id"))
        }
    }
}
