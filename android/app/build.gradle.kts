import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

fun readProps(path: String): Properties = Properties().apply {
    val file = rootProject.file(path)
    if (file.exists()) file.reader(Charsets.UTF_8).use { load(it) }
}

val versionProps = readProps("version.properties")
val appVersionCode = (versionProps.getProperty("versionCode") ?: "1").trim().toInt()
val appVersionName = (versionProps.getProperty("versionName") ?: "1.0.0").trim()

val keystoreProps = readProps("keystore.properties")
val releaseKeyFile = keystoreProps.getProperty("storeFile")
    ?.let { rootProject.file(it) }
    ?.takeIf { it.exists() }

// Без ключа release-сборка не должна молча подписываться debug-ключом:
// такое приложение не установится поверх и сломает обновления.
val releaseRequested = gradle.startParameter.taskNames.any {
    it.contains("release", ignoreCase = true) ||
        it.contains("bundle", ignoreCase = true) ||
        it.contains("rustore", ignoreCase = true)
}
if (releaseKeyFile == null && releaseRequested) {
    throw GradleException(
        "keystore.properties не найден или storeFile не существует. " +
            "Release-сборка без ключа подписи запрещена."
    )
}

android {
    namespace = "ru.fvkhweb.movies"
    compileSdk = 35

    defaultConfig {
        applicationId = "ru.fvkhweb.movies"
        minSdk = 26
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName
        // Сборка rustore переопределяет на false: никаких обновлений с GitHub.
        buildConfigField("boolean", "AUTOUPDATE_ENABLED", "true")
    }

    signingConfigs {
        if (releaseKeyFile != null) {
            create("release") {
                storeFile = releaseKeyFile
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            // Debug-сборка сразу видна в системе: версия 1.0.1-debug, свой ключ.
            // Раздавать её людям нельзя — обновления с ней не встанут.
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            // null допустим только при запуске не-release задач; проверка выше
            // не даст собрать release без keystore.properties
            signingConfig = if (releaseKeyFile != null) {
                signingConfigs.getByName("release")
            } else {
                null
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        // Для RuStore: та же подпись и версия, но без клиента автообновления.
        create("rustore") {
            initWith(getByName("release"))
            buildConfigField("boolean", "AUTOUPDATE_ENABLED", "false")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)

    implementation(libs.androidx.navigation.compose)
    implementation(libs.coil.compose)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.work.runtime.ktx)

    debugImplementation(libs.androidx.ui.tooling)
}
